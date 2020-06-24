import os
import subprocess
import tempfile
from binary_vars import *


libvpx_threads = 4


def rav1e_command(job, temp_dir):
    """
    Given a job config and a temporary directory prepare an aom 
    command to encode the file and output it in the temporary directory
    This function returns the command to run the encoder

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

      temp_dir: str
    Returns:
        (command, encoder_files) where:
            command: List of command with args
            encoder_files: Dictionary containing output file path, spatial-layer
                and temporal-layer
    """
    assert job['num_spatial_layers'] == 1
    assert job['num_temporal_layers'] == 1
    assert job['codec'] == 'av1'
    assert job['encoder'] == 'rav1e-1pass'

    (fd, encoded_filename) = tempfile.mkstemp(dir=temp_dir, suffix=".ivf")
    os.close(fd)

    clip = job['clip']
    fps = int(clip['fps'] + 0.5)

    common_params = [
        '-y',
        '--output', encoded_filename,
        '--bitrate', str(job['target_bitrates_kbps'][0]),
        clip['input_file']
    ]
    
    encoder = job['encoder'] = 'rav1e-1pass'

    if encoder == 'rav1e-1pass':
        codec_params = [
            '--speed', '4',
            '--low-latency',
            '--keyint', '60'
        ]



    command = [RAV1E_ENC_BIN] + codec_params + common_params

    encoded_files = [{'spatial-layer': 0,
                      'temporal-layer': 0, 'filename': encoded_filename
                      }]

    return command, encoded_files


def svt_command(job, temp_dir):
    """
    Given a job config and a temporary directory prepare an aom 
    command to encode the file and output it in the temporary directory
    This function returns the command to run the encoder

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

      temp_dir: str
    Returns:
        (command, encoder_files) where:
            command: List of command with args
            encoder_files: Dictionary containing output file path, spatial-layer
                and temporal-layer
    """
    assert job['num_spatial_layers'] == 1
    assert job['num_temporal_layers'] == 1
    assert job['codec'] == 'av1'
    assert job['encoder'] in ['svt-1pass', 'svt-rt', 'svt-fqp']

    (fd, encoded_filename) = tempfile.mkstemp(dir=temp_dir, suffix=".ivf")
    os.close(fd)

    clip = job['clip']
    fps = int(clip['fps'] + 0.5)

    common_params = [
        '-fps', str(fps),
        '-tbr', str(job['target_bitrates_kbps'][0]),
        '-w', str(clip['width']),
        '-h', str(clip['height']),
        '-i', str(clip['yuv_file']),
        '-b', encoded_filename
    ]

    encoder = job['encoder']
    
    if encoder == 'svt-1pass':

        codec_params = [
            '--rc', "2",
            '-q', "20",
            '--preset', "8",
        ]
    elif encoder == 'svt-rt':

        codec_params = [
            '--scm', '0',
            '--lookahead', '0',
            '--preset', '8',
            '--keyint', '59'
        ]
    elif encoder == 'svt-fqp': # Fixed qp
        
        codec_params = [
            '--rc', "0",
            '-q', "25",
            "--min-qp", '20',
            '--max-qp', '28',
        ]
    
    command = [SVT_ENC_BIN] + codec_params + common_params

    encoded_files = [{'spatial-layer': 0,
                      'temporal-layer': 0, 'filename': encoded_filename
                      }]

    return command, encoded_files


def aom_command(job, temp_dir):
    """
    Given a job config and a temporary directory prepare an aom 
    command to encode the file and output it in the temporary directory
    This function returns the command to run the encoder

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

      temp_dir: str
    Returns:
        (command, encoder_files) where:
            command: List of command with args
            encoder_files: Dictionary containing output file path, spatial-layer
                and temporal-layer
    """
    assert job['num_spatial_layers'] == 1
    assert job['num_temporal_layers'] == 1
    assert job['codec'] == 'av1'
    # TODO(pbos): Add realtime config (aom-rt) when AV1 is realtime ready.
    assert job['encoder'] in ['aom-good', 'aom-rt', 'aom-all_intra', 'aom-offline']

    (fd, first_pass_file) = tempfile.mkstemp(dir=temp_dir, suffix=".fpf")
    os.close(fd)

    (fd, encoded_filename) = tempfile.mkstemp(dir=temp_dir, suffix=".webm")
    os.close(fd)

    clip = job['clip']
    fps = int(clip['fps'] + 0.5)

    common_params = [
        '--codec=av1',
        '--width=%d' % clip['width'],
        '--height=%d' % clip['height'],
        '--output=%s' % encoded_filename,
        '--target-bitrate=%d' % job['target_bitrates_kbps'][0],
        '--output=%s' % encoded_filename,
        clip['yuv_file']
    ]

    encoder = job['encoder']

    if encoder == 'aom-good':
        codec_params = [
            '--good',
            "-p", "2",
            "--lag-in-frames=25",
            '--cpu-used=3',
            "--min-q=0",
            "--max-q=63",
            "--auto-alt-ref=1",
            "--kf-max-dist=150",
            "--kf-min-dist=0",
            "--drop-frame=0",
            "--static-thresh=0",
            "--bias-pct=50",
            "--minsection-pct=0",
            "--maxsection-pct=2000",
            "--arnr-maxframes=7",
            "--arnr-strength=5",
            "--sharpness=0",
            "--undershoot-pct=100",
            "--overshoot-pct=100",
            "--frame-parallel=0",
            "--tile-columns=0",
            "--profile=0"
        ]

    elif encoder == 'aom-all_intra':
        codec_params = [
            '--cpu-used=4',
            '--kf-max-dist=1',
            '--end-usage=q'
        ]
    elif encoder == 'aom-rt':
        codec_params = [
            '--cpu-used=4',
            '--enable-tpl-model=0',
            '--deltaq-mode=0',
            '--sb-size=0',
            '--ivf',
            '--profile=0',
            '--static-thresh=0',
            '--undershoot-pct=50',
            '--overshoot-pct=50',
            '--buf-sz=1000',
            '--buf-initial-sz=500',
            '--buf-optimal-sz=600',
            '--max-intra-rate=300',
            '--passes=1',
            '--rt',
            '--lag-in-frames=0',
            '--noise-sensitivity=0',
            '--error-resilient=1',
        ]
    elif encoder == 'aom-offline':
        codec_params = [
            '--good',
            "--passes=2",
            '--threads=0',
            "--lag-in-frames=25",
            '--cpu-used=2',
            "--min-q=0",
            "--max-q=63",
            "--auto-alt-ref=1",
            "--kf-max-dist=150",
            "--kf-min-dist=0",
            "--drop-frame=0",
            "--static-thresh=0",
            "--bias-pct=50",
            "--minsection-pct=0",
            "--maxsection-pct=2000",
            "--arnr-maxframes=7",
            "--arnr-strength=5",
            "--sharpness=0",
            "--undershoot-pct=25",
            "--overshoot-pct=25",
            "--frame-parallel=1",
            "--tile-columns=3",
            "--profile=0"
        ]
    # command = [
    #     AOM_ENC_BIN,
    #     "--codec=av1",
    #     "-p", "2",
    #     "--fpf=%s" % first_pass_file,
    #     "--good",
    #     "--cpu-used=8",
    #     "--target-bitrate=%d" % job['target_bitrates_kbps'][0],
    #     '--fps=%d/1' % fps,
    #     "--lag-in-frames=25",
    #     "--min-q=0",
    #     "--max-q=63",
    #     "--auto-alt-ref=1",
    #     "--kf-max-dist=150",
    #     "--kf-min-dist=0",
    #     "--drop-frame=0",
    #     "--static-thresh=0",
    #     "--bias-pct=50",
    #     "--minsection-pct=0",
    #     "--maxsection-pct=2000",
    #     "--arnr-maxframes=7",
    #     "--arnr-strength=5",
    #     "--sharpness=0",
    #     "--undershoot-pct=100",
    #     "--overshoot-pct=100",
    #     "--frame-parallel=0",
    #     "--tile-columns=0",
    #     "--profile=0",
    #     '--width=%d' % clip['width'],
    #     '--height=%d' % clip['height'],
    #     '--output=%s' % encoded_filename,
    #     clip['yuv_file'],
    # ]

    command = [AOM_ENC_BIN] + codec_params + common_params

    encoded_files = [{'spatial-layer': 0,
                      'temporal-layer': 0, 'filename': encoded_filename}]
    return (command, encoded_files)


def libvpx_tl_command(job, temp_dir):
    # Parameters are intended to be as close as possible to realtime settings used
    # in WebRTC.
    assert job['num_temporal_layers'] <= 3
    # TODO(pbos): Account for low resolution CPU levels (see below).
    codec_cpu = 6 if job['codec'] == 'vp8' else 7
    layer_strategy = 8 if job['num_temporal_layers'] == 2 else 10
    outfile_prefix = '%s/out' % temp_dir
    clip = job['clip']
    fps = int(clip['fps'] + 0.5)

    command = [
        VPX_SVC_ENC_BIN,
        clip['yuv_file'],
        outfile_prefix,
        job['codec'],
        clip['width'],
        clip['height'],
        '1',
        fps,
        codec_cpu,
        '0',
        libvpx_threads,
        layer_strategy
    ] + job['target_bitrates_kbps']
    command = [str(i) for i in command]
    encoded_files = [{'spatial-layer': 0, 'temporal-layer': i, 'filename': "%s_%d.ivf" % (
        outfile_prefix, i)} for i in range(job['num_temporal_layers'])]

    return ([str(i) for i in command], encoded_files)


def libvpx_command(job, temp_dir):
    # Parameters are intended to be as close as possible to realtime settings used
    # in WebRTC.
    if (job['num_temporal_layers'] > 1):
        return libvpx_tl_command(job, temp_dir)
    assert job['num_spatial_layers'] == 1
    # TODO(pbos): Account for low resolutions (use -4 and 5 for CPU levels).
    common_params = [
        "--lag-in-frames=0",
        "--error-resilient=1",
        "--kf-min-dist=3000",
        "--kf-max-dist=3000",
        "--static-thresh=1",
        "--end-usage=cbr",
        "--undershoot-pct=100",
        "--overshoot-pct=15",
        "--buf-sz=1000",
        "--buf-initial-sz=500",
        "--buf-optimal-sz=600",
        "--max-intra-rate=900",
        "--resize-allowed=0",
        "--drop-frame=0",
        "--passes=1",
        "--rt",
        "--noise-sensitivity=0",
        "--threads=%d" % libvpx_threads,
    ]
    if job['codec'] == 'vp8':
        codec_params = [
            "--codec=vp8",
            "--cpu-used=-6",
            "--min-q=2",
            "--max-q=56",
            "--screen-content-mode=0",
        ]
    elif job['codec'] == 'vp9':
        codec_params = [
            "--codec=vp9",
            "--cpu-used=7",
            "--min-q=2",
            "--max-q=52",
            "--aq-mode=3",
        ]

    (fd, encoded_filename) = tempfile.mkstemp(dir=temp_dir, suffix=".webm")
    os.close(fd)

    clip = job['clip']
    # Round FPS. For quality comparisons it's likely close enough to not be
    # misrepresentative. From a quality perspective there's no point to fully
    # respecting NTSC or other non-integer FPS formats here.
    fps = int(clip['fps'] + 0.5)

    command = [VPX_ENC_BIN] + codec_params + common_params + [
        '--fps=%d/1' % fps,
        '--target-bitrate=%d' % job['target_bitrates_kbps'][0],
        '--width=%d' % clip['width'],
        '--height=%d' % clip['height'],
        '--output=%s' % encoded_filename,
        clip['yuv_file']
    ]
    encoded_files = [{'spatial-layer': 0,
                      'temporal-layer': 0, 'filename': encoded_filename}]
    return (command, encoded_files)


def openh264_command(job, temp_dir):
    """
    Given a job config and a temporary directory prepare an aom 
    command to encode the file and output it in the temporary directory
    This function returns the command to run the encoder

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

      temp_dir: str
    Returns:
        (command, encoder_files) where:
            command: List of command with args
            encoder_files: Dictionary containing output file path, spatial-layer
                and temporal-layer
    """
    assert job['codec'] == 'h264'
    # TODO(pbos): Consider AVC support.
    assert job['num_spatial_layers'] == 1
    # TODO(pbos): Add temporal-layer support (-numtl).
    assert job['num_temporal_layers'] == 1

    (fd, encoded_filename) = tempfile.mkstemp(dir=temp_dir, suffix=".264")
    os.close(fd)

    clip = job['clip']

    command = [
        H264_ENC_BIN,
        '-rc', 1,
        '-denois', 0,
        '-scene', 0,
        '-bgd', 0,
        '-fs', 0,
        '-tarb', job['target_bitrates_kbps'][0],
        '-sw', clip['width'],
        '-sh', clip['height'],
        '-frin', clip['fps'],
        '-org', clip['yuv_file'],
        '-bf', encoded_filename,
        '-numl', 1,
        '-dw', 0, clip['width'],
        '-dh', 0, clip['height'],
        '-frout', 0, clip['fps'],
        '-ltarb', 0, job['target_bitrates_kbps'][0],
    ]
    encoded_files = [{'spatial-layer': 0,
                      'temporal-layer': 0, 'filename': encoded_filename}]
    return ([str(i) for i in command], encoded_files)


def yami_command(job, temp_dir):
    """
    Given a job config and a temporary directory prepare an aom 
    command to encode the file and output it in the temporary directory
    This function returns the command to run the encoder

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

      temp_dir: str
    Returns:
        (command, encoder_files) where:
            command: List of command with args
            encoder_files: Dictionary containing output file path, spatial-layer
                and temporal-layer
    """
    assert job['num_spatial_layers'] == 1
    assert job['num_temporal_layers'] == 1

    (fd, encoded_filename) = tempfile.mkstemp(dir=temp_dir, suffix=".ivf")
    os.close(fd)

    clip = job['clip']
    # Round FPS. For quality comparisons it's likely close enough to not be
    # misrepresentative. From a quality perspective there's no point to fully
    # respecting NTSC or other non-integer FPS formats here.
    fps = int(clip['fps'] + 0.5)

    command = [
        YAMI_ENC_BIN,
        '--rcmode', 'CBR',
        '--ipperiod', 1,
        '--intraperiod', 3000,
        '-c', job['codec'].upper(),
        '-i', clip['yuv_file'],
        '-W', clip['width'],
        '-H', clip['height'],
        '-f', fps,
        '-o', encoded_filename,
        '-b', job['target_bitrates_kbps'][0],
    ]
    encoded_files = [{'spatial-layer': 0,
                      'temporal-layer': 0, 'filename': encoded_filename}]
    return ([str(i) for i in command], encoded_files)

def get_encoder_command(encoder):
    encoders = [
        'aom-good', 'aom-rt', 'aom-all_intra', 'aom-offline', ## AOM CONFIGS
        'rav1e-1pass', ## RAV1E CONFIGS
        'svt-1pass', 'svt-rt', 'svt-fqp', ## SVT CONFIGS
        'openh264', ## OPENH264 CONFIGS
        'libvpx-rt', ## LIBVPX CONFIGS
        'yami' ## YAMI CONFIGS
    ]

    if encoder not in encoders:
        return None

    if 'aom' in encoder:
        return aom_command
    elif 'rav1e' in encoder:
        return rav1e_command
    elif 'svt' in encoder:
        return svt_command
    elif 'libvpx' in encoder:
        return libvpx_command
    elif 'openh264' in encoder:
        return openh264_command
    elif 'yami' in encoder:
        return yami_command
