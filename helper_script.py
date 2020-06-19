def run_encoder_command(job, encoder_command, job_temp_dir, encoded_file_dir):
    """
    This function will run the external encoder command and generate the metrics for
    the encoded file

    Args:
        job: {
          'encoder': str,
          'codec': str,
          'clip': {
              'file_type': str,
              'input_file': str,
              'height': int,
              'width': int,
              'fps': float,
              'yuv_file': str,
              'sha1sum': str,
              'input_total_frames': float
          },
          'target_bitrate_kbps': List[int],
          'num_spatial_layers': int,
          'num_temporal_layers': int
        }

        encoder_command: Tuple(
            List[str], # The command to run
            List[{
                'filename': str,
                'temporal-layer': str,
                'spatial-layer': str
            }]
        )

        job_temp_dir: str

        encoded_file_dir: str | None
    Returns:
        A tuple containing information about the results and the output
        from the external encoder process
    """

    # Get the command to run the encoder
    (command, encoded_files) = encoder_command

    # Metadata about the file
    clip = job['clip']

    # Start timing the encode time
    start_time = time.time()
    try:
        # Run the encoder process externally
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except OSError as e:
        return (None, "> %s\n%s" % (" ".join(command), e))
    # Wait for external process to finish
    (output, _) = process.communicate()

    # Measure the encoding time
    actual_encode_ms = (time.time() - start_time) * 1000

    # Get file information
    input_yuv_filesize = os.path.getsize(clip['yuv_file'])
    input_num_frames = int(input_yuv_filesize /
                           (6 * clip['width'] * clip['height'] / 4))
    target_encode_ms = float(input_num_frames) * 1000 / clip['fps']

    if process.returncode != 0:
        return (None, "> %s\n%s" % (" ".join(command), output))

    # Generate file metadata and output file results
    results = [{} for i in range(len(encoded_files))]

    for i in range(len(results)):
        results_dict = results[i]
        results_dict['input-file'] = os.path.basename(clip['input_file'])
        results_dict['input-file-sha1sum'] = clip['sha1sum']
        results_dict['input-total-frames'] = clip['input_total_frames']
        results_dict['frame-offset'] = args.frame_offset
        results_dict['bitrate-config-kbps'] = job['target_bitrates_kbps']
        results_dict['layer-pattern'] = "%dsl%dtl" % (
            job['num_spatial_layers'], job['num_temporal_layers'])
        results_dict['encoder'] = job['encoder']
        results_dict['codec'] = job['codec']
        results_dict['height'] = clip['height']
        results_dict['width'] = clip['width']
        results_dict['fps'] = clip['fps']
        results_dict['actual-encode-time-ms'] = actual_encode_ms
        results_dict['target-encode-time-ms'] = target_encode_ms
        results_dict['encode-time-utilization'] = actual_encode_ms / \
            target_encode_ms
        layer = encoded_files[i]

        results_dict['temporal-layer'] = layer['temporal-layer']
        results_dict['spatial-layer'] = layer['spatial-layer']

        # Generate the metrics for the output encoded file
        generate_metrics(results_dict, job, job_temp_dir, layer)

        if encoded_file_dir:
            # TODO: Figure this out
            encoded_file_pattern = "%s-%s-%s-%dsl%dtl-%d-sl%d-tl%d%s" % (os.path.splitext(os.path.basename(clip['input_file']))[
                                                                         0], job['encoder'], job['codec'], job['num_spatial_layers'], job['num_temporal_layers'], job['target_bitrates_kbps'][-1], layer['spatial-layer'], layer['temporal-layer'], os.path.splitext(layer['filename'])[1])
            shutil.move(layer['filename'], os.path.join(
                encoded_file_dir, encoded_file_pattern))
        else:
            os.remove(layer['filename'])

    shutil.rmtree(job_temp_dir)

    # Return the results information along with encoder process' stdout
    return (results, output)


def run_tiny_ssim(results_dict, job, temp_dir, encoded_file):
    # Decode the video to generate a yuv file
    (decoded_file, decoder_framestats) = decode_file(
        job, temp_dir, encoded_file['filename'])
    clip = job['clip']
    temporal_divide = 2 ** (job['num_temporal_layers'] -
                            1 - encoded_file['temporal-layer'])
    temporal_skip = temporal_divide - 1

     ssim_command = 'libvpx/tools/tiny_ssim', clip['yuv_file'], decoded_file, "%dx%d" % (
        results_dict['width'], results_dict['height']), str(temporal_skip)]
    if args.enable_frame_metrics:
        # TODO(pbos): Perform SSIM on downscaled .yuv files for spatial layers.
        (fd, metrics_framestats) = tempfile.mkstemp(dir=temp_dir, suffix=".csv")
        os.close(fd)
        ssim_command.append(metrics_framestats)


    # Run the metrics command to generate the metrics
    ssim_results = subprocess.check_output(ssim_command, encoding='utf-8').splitlines()

    # Parse the metrics file
    metric_map = {
        'AvgPSNR': 'avg-psnr',
        'AvgPSNR-Y': 'avg-psnr-y',
        'AvgPSNR-U': 'avg-psnr-u',
        'AvgPSNR-V': 'avg-psnr-v',
        'GlbPSNR': 'glb-psnr',
        'GlbPSNR-Y': 'glb-psnr-y',
        'GlbPSNR-U': 'glb-psnr-u',
        'GlbPSNR-V': 'glb-psnr-v',
        'SSIM': 'ssim',
        'SSIM-Y': 'ssim-y',
        'SSIM-U': 'ssim-u',
        'SSIM-V': 'ssim-v',
        'VpxSSIM': 'vpx-ssim',
    }

    # Parse the metrics file
    for line in ssim_results:
        if not line:
            continue
        (metric, value) = line.split(': ')
        if metric in metric_map:
            results_dict[metric] = float(value)
        elif metric == 'Nframes':
            layer_frames = int(value)
            results_dict['frame-count'] = layer_frames

    if decoder_framestats and args.enable_frame_metrics:
        add_framestats(results_dict, decoder_framestats, int)
    add_framestats(results_dict, metrics_framestats, float)

    layer_fps = clip['fps'] / temporal_divide
    results_dict['layer-fps'] = layer_fps

def generate_metrics(results_dict, job, temp_dir, encoded_file):
    """
    Given an encoded file, decode it and generate some metrics around it.
    Currently, the rtc metrics are generated using the `libvpx/tools/tiny_ssim command`

    """
    # Decode the video to generate a yuv file
    (decoded_file, decoder_framestats) = decode_file(
        job, temp_dir, encoded_file['filename'])
    clip=job['clip']
    temporal_divide=2 ** (job['num_temporal_layers'] -
                            1 - encoded_file['temporal-layer'])
    temporal_skip=temporal_divide - 1

    (fd, metrics_framestats)=tempfile.mkstemp(dir = temp_dir, suffix = ".csv")
    os.close(fd)

    # Run the metrics command to generate the metrics
    ssim_results=subprocess.check_output(['libvpx/tools/tiny_ssim', clip['yuv_file'], decoded_file, "%dx%d" % (
        results_dict['width'], results_dict['height']), str(temporal_skip), metrics_framestats], encoding = 'utf-8').splitlines()

    # Parse the metrics file
    metric_map={
        'AvgPSNR': 'avg-psnr',
        'AvgPSNR-Y': 'avg-psnr-y',
        'AvgPSNR-U': 'avg-psnr-u',
        'AvgPSNR-V': 'avg-psnr-v',
        'GlbPSNR': 'glb-psnr',
        'GlbPSNR-Y': 'glb-psnr-y',
        'GlbPSNR-U': 'glb-psnr-u',
        'GlbPSNR-V': 'glb-psnr-v',
        'SSIM': 'ssim',
        'SSIM-Y': 'ssim-y',
        'SSIM-U': 'ssim-u',
        'SSIM-V': 'ssim-v',
        'VpxSSIM': 'vpx-ssim',
    }

    # Parse the metrics file
    for line in ssim_results:
        if not line:
            continue
        (metric, value) = line.split(': ')
        if metric in metric_map:
            results_dict[metric_map[metric]] = float(value)
        elif metric == 'Nframes':
            layer_frames = int(value)
            results_dict['frame-count'] = layer_frames

    if decoder_framestats:
        add_framestats(results_dict, decoder_framestats, int)
    add_framestats(results_dict, metrics_framestats, float)


    # VMAF option if enabled. TODO: Remove this
    if args.enable_vmaf:
        results_file = 'sample.json'
        vmaf_results = subprocess.check_output(['vmaf/libvmaf/build/tools/vmafossexec', 'yuv420p', str(results_dict['width']), str(
            results_dict['height']), clip['yuv_file'], decoded_file, 'vmaf/model/vmaf_v0.6.1.pkl', '--log-fmt', 'json', '--log', results_file], encoding='utf-8')
        # vmaf_obj = json.loads(vmaf_results)
        with open('sample.json', 'r') as results_file:
            vmaf_obj = json.load(results_file)

        results_dict['vmaf'] = float(vmaf_obj['aggregate']['VMAF_score'])

        results_dict['frame-vmaf'] = []
        for frame in vmaf_obj['frames']:
            results_dict['frame-vmaf'].append(frame['VMAF_score'])

    layer_fps = clip['fps'] / temporal_divide
    results_dict['layer-fps'] = layer_fps

    spatial_divide = 2 ** (job['num_spatial_layers'] -
                           1 - encoded_file['spatial-layer'])
    results_dict['layer-width']=results_dict['width'] // spatial_divide
    results_dict['layer-height']=results_dict['height'] // spatial_divide


    # Calculate and compare target bitrate with actual bitrate used
    target_bitrate_bps=job['target_bitrates_kbps'][encoded_file['temporal-layer']] * 1000
    bitrate_used_bps=os.path.getsize(
        encoded_file['filename']) * 8 * layer_fps / layer_frames
    results_dict['target-bitrate-bps'] = target_bitrate_bps
    results_dict['actual-bitrate-bps'] = bitrate_used_bps
    results_dict['bitrate-utilization'] = float(
        bitrate_used_bps) / target_bitrate_bps

def prepare_clips(args, temp_dir):
    """
    Given args object and temporary directory, prepare the clips for the pipeline. 
    We do this by the following steps:

    * Convert all y4m to yuv and store in tmp dir
    * Get sha1sum for the converted yuv files
    * Store the height and width of the clips
    * Store the total number of frames and the size of the file
    """
    clips = args.clips
    # TODO: do not convert y4m if cargo encoder is being used
    y4m_clips = [clip for clip in clips if clip['file_type'] == 'y4m']

    # Convert all y4m clips to yuv using ffmpeg
    if y4m_clips:
        print("Converting %d .y4m clip%s..." %
              (len(y4m_clips), "" if len(y4m_clips) == 1 else "s"))
        for clip in y4m_clips:
            (fd, yuv_file) = tempfile.mkstemp(dir=temp_dir,
                                              suffix=".%d_%d.yuv" % (clip['width'], clip['height']))
            os.close(fd)
            with open(os.devnull, 'w') as devnull:
                subprocess.check_call(
                    ['ffmpeg', '-y', '-i', clip['input_file'], yuv_file], stdout=devnull, stderr=devnull)
            clip['yuv_file'] = yuv_file

    # Get sha1sum of file and other metadata
    for clip in clips:
        clip['sha1sum'] = subprocess.check_output(
            ['sha1sum', clip['input_file']], encoding='utf-8').split(' ', 1)[0]
        if 'yuv_file' not in clip:
            clip['yuv_file'] = clip['input_file']
        frame_size = 6 * clip['width'] * clip['height'] / 4
        input_yuv_filesize = os.path.getsize(clip['yuv_file'])
        clip['input_total_frames'] = input_yuv_filesize / frame_size
        # Truncate file if necessary.
        if args.frame_offset > 0 or args.num_frames > 0:
            (fd, truncated_filename) = tempfile.mkstemp(
                dir=temp_dir, suffix=".yuv")
            blocksize = 2048 * 1024
            total_filesize = args.num_frames * frame_size
            with os.fdopen(fd, 'wb', blocksize) as truncated_file:
                with open(clip['yuv_file'], 'rb') as original_file:
                    original_file.seek(args.frame_offset * frame_size)
                    while total_filesize > 0:
                        data = original_file.read(
                            blocksize if blocksize < total_filesize else total_filesize)
                        truncated_file.write(data)
                        total_filesize -= blocksize
            clip['yuv_file'] = truncated_filename

