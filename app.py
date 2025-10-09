from flask import Flask, request, render_template, jsonify, send_file
from flask import make_response
from openai import OpenAI
import os
import sys
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path
import uuid
from PIL import Image
import logging
import sys # sysモジュールは再度必要になるのでインポートを戻します
from moviepy.editor import VideoFileClip # moviepyのインポートを追加
import subprocess
try:
    import imageio_ffmpeg
except Exception:
    imageio_ffmpeg = None

load_dotenv()

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# ログ設定: app.logファイルにログを出力します
log_file_path = Path(__file__).parent / "app.log"
logging.basicConfig(
    filename=log_file_path, # app.logにログを出力
    level=logging.DEBUG,     # デバッグレベル以上のログを出力
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
# Flaskのロガーもファイルに出力するように設定（stdoutへの追加は削除）
app.logger.setLevel(logging.DEBUG)

# ログ出力用の関数は不要になるので削除
# def log(msg):
#     print(msg, flush=True)

static_dir = Path('static')
static_dir.mkdir(exist_ok=True)

# 起動時に7日前のファイルを削除
def cleanup_old_files():
    seven_days_ago = time.time() - (7 * 24 * 60 * 60)
    for file in static_dir.glob('*.mp4'):
        if file.stat().st_mtime < seven_days_ago:
            file.unlink()
            app.logger.info(f'削除: {file.name}')

cleanup_old_files()

def extract_last_frame(video_path: Path, last_frame_path: Path) -> bool:
    """動画の最終付近のフレームをPNGで保存。moviepyが失敗したらffmpegでフォールバック。"""
    def _ok(p: Path) -> bool:
        try:
            return p.exists() and p.stat().st_size > 0
        except Exception:
            return False

    def _rename_tmp(tmp: Path, dst: Path) -> bool:
        try:
            if _ok(tmp):
                tmp.replace(dst)
                return True
            return False
        except Exception as e:
            app.logger.error(f'rename失敗: {tmp} -> {dst}: {e}', exc_info=True)
            return False

    # まずmoviepy
    try:
        clip = VideoFileClip(str(video_path))
        last_frame_time = max(0.0, (clip.duration or 0) - 0.2)
        # 一時ファイルも .png 拡張子を保持（ツールが形式判定可能にするため）
        tmp = last_frame_path.with_name(f".tmp_{uuid.uuid4()}_{last_frame_path.name}")
        clip.save_frame(str(tmp), t=last_frame_time)
        clip.close()
        if _rename_tmp(tmp, last_frame_path):
            app.logger.info(f'最終フレームを抽出して保存しました(moviepy): {last_frame_path}')
            return True
        else:
            app.logger.warning(f'moviepyで保存した一時ファイルが不正: {tmp}')
    except Exception as e:
        app.logger.warning(f'moviepyでの抽出に失敗。ffmpegで再試行します: {e}')
    # ffmpeg CLI フォールバック
    ffmpeg_path = None
    if imageio_ffmpeg:
        try:
            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg_path = None
    if not ffmpeg_path:
        ffmpeg_path = 'ffmpeg'
    # 方式1: sseof（終端相対）
    # ffmpeg 出力も .png のままの一時ファイルに出力
    tmp1 = last_frame_path.with_name(f".tmp_{uuid.uuid4()}_{last_frame_path.name}")
    cmd1 = [ffmpeg_path, '-y', '-v', 'error', '-sseof', '-0.2', '-i', str(video_path), '-frames:v', '1', str(tmp1)]
    try:
        r = subprocess.run(cmd1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        if _rename_tmp(tmp1, last_frame_path):
            app.logger.info(f'最終フレームを抽出して保存しました(ffmpeg sseof): {last_frame_path}')
            return True
        else:
            app.logger.warning(f'ffmpeg sseof 実行後に出力が見つかりませんでした: {tmp1}; stderr={r.stderr.decode(errors="ignore")[:300]}')
    except subprocess.CalledProcessError as e:
        app.logger.warning(f'ffmpeg sseof 失敗: {e.stderr.decode(errors="ignore")[:300]}')

    # 方式2: durationから-0.2sを絶対指定
    duration = None
    try:
        clip2 = VideoFileClip(str(video_path))
        duration = clip2.duration or 0.0
        clip2.close()
    except Exception:
        # ffprobeで取得
        try:
            r = subprocess.run([ffmpeg_path.replace('ffmpeg','ffprobe'), '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nokey=1:noprint_wrappers=1', str(video_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            duration = float(r.stdout.decode().strip())
        except Exception as e:
            app.logger.warning(f'duration取得に失敗: {e}')
            duration = 0.0
    t = max(0.0, (duration or 0.0) - 0.2)
    tmp2 = last_frame_path.with_name(f".tmp_{uuid.uuid4()}_{last_frame_path.name}")
    cmd2 = [ffmpeg_path, '-y', '-v', 'error', '-ss', f'{t:.2f}', '-i', str(video_path), '-frames:v', '1', str(tmp2)]
    try:
        r2 = subprocess.run(cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        if _rename_tmp(tmp2, last_frame_path):
            app.logger.info(f'最終フレームを抽出して保存しました(ffmpeg -ss): {last_frame_path}')
            return True
        else:
            app.logger.error(f'ffmpeg -ss 実行後に出力が見つかりませんでした: {tmp2}; stderr={r2.stderr.decode(errors="ignore")[:300]}')
            return False
    except subprocess.CalledProcessError as e:
        app.logger.error(f'ffmpeg -ss 失敗: {e.stderr.decode(errors="ignore")[:300]}', exc_info=True)
        return False

@app.route('/')
def index():
    resp = make_response(render_template('index.html'))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/generate', methods=['POST'])
def generate():
    prompt = request.form.get('prompt')
    model = request.form.get('model', 'sora-2')
    seconds = request.form.get('seconds', '8')
    size = request.form.get('size', '1280x720')
    image_file = request.files.get('image_file')
    image_path = None
    resize_info = ""

    if not prompt and not image_file:
        app.logger.warning('プロンプトまたは画像がありません')
        return jsonify({'error': 'プロンプトまたは画像をアップロードしてください'}), 400

    if image_file:
        # 一時的に画像を保存
        image_filename = f"{uuid.uuid4()}_{image_file.filename}"
        original_image_path = static_dir / image_filename
        image_file.save(original_image_path)
        app.logger.info(f'[DEBUG] Original image saved to: {original_image_path}')

        # 画像のリサイズとクロップ処理
        try:
            img = Image.open(original_image_path)
            img_width, img_height = img.size
            target_width, target_height = map(int, size.split('x'))

            if img_width != target_width or img_height != target_height:
                app.logger.info(f'[DEBUG] Resizing image from {img_width}x{img_height} to {target_width}x{target_height}')
                # アスペクト比を計算
                img_aspect = img_width / img_height
                target_aspect = target_width / target_height

                if img_aspect > target_aspect:  # 元画像が横長の場合、高さを合わせる
                    new_height = target_height
                    new_width = int(new_height * img_aspect)
                else:  # 元画像が縦長の場合、幅を合わせる
                    new_width = target_width
                    new_height = int(new_width / img_aspect)

                # リサイズ
                img = img.resize((new_width, new_height), Image.LANCZOS)
                app.logger.info(f'[DEBUG] Resized to {new_width}x{new_height}')

                # クロップ
                left = (new_width - target_width) / 2
                top = (new_height - target_height) / 2
                right = (new_width + target_width) / 2
                bottom = (new_height + target_height) / 2
                img = img.crop((left, top, right, bottom))
                app.logger.info(f'[DEBUG] Cropped to {target_width}x{target_height}')

                # リサイズ/クロップされた画像を新しいパスに保存
                resized_image_filename = f"resized_{image_filename}"
                image_path = static_dir / resized_image_filename
                img.save(image_path)
                resize_info = "画像が動画サイズに合わせて調整されました。"
                app.logger.info(f'[DEBUG] Resized/cropped image saved to: {image_path}')
            else:
                # リサイズ不要な場合は元のパスを使用
                image_path = original_image_path
                app.logger.info(f'[DEBUG] Image size matches, no resize/crop needed.')

        except Exception as e:
            app.logger.error(f'画像処理エラー: {str(e)}', exc_info=True)

    app.logger.debug(f'[DEBUG] Generate request: model={model}, seconds={seconds}, size={size}, prompt={prompt[:50]}...')

    try:
        params = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "seconds": seconds
        }
        if image_path:
            params["input_reference"] = image_path.open("rb") # APIにはリサイズ/クロップされた後のファイルパスを渡す
            app.logger.debug(f'[DEBUG] Image file used for API: {image_path}')

        video = client.videos.create(
            **params
        )
        app.logger.info(f'[DEBUG] Video created: id={video.id}, status={video.status}')
        return jsonify({'video_id': video.id, 'status': video.status, 'resize_info': resize_info})
    except Exception as e:
        app.logger.error(f'ビデオ生成エラー: {str(e)}', exc_info=True)

@app.route('/status/<video_id>')
def check_status(video_id):
    try:
        video = client.videos.retrieve(video_id)

        app.logger.debug(f'[DEBUG] video_id={video_id}, status={video.status}, progress={getattr(video, "progress", None)}')
        app.logger.debug(f'[DEBUG] video object: {video}')

        if video.status == 'completed':
            app.logger.info(f'[DEBUG] Status is completed, starting download...')
            video_path = static_dir / f'{video_id}.mp4'
            last_frame_path = static_dir / f"{video_id}_last_frame.png"

            if not video_path.exists():
                app.logger.info(f'[DEBUG] File does not exist, downloading...')
                try:
                    # 直接URLを取得してダウンロード（タイムアウト付き）
                    import requests

                    # ビデオURLを取得
                    video_data = video.model_dump() if hasattr(video, 'model_dump') else video.__dict__
                    app.logger.debug(f'[DEBUG] Video data: {video_data}')

                    # URLを探す
                    video_url = None
                    if 'url' in video_data:
                        video_url = video_data['url']
                    elif 'video_url' in video_data:
                        video_url = video_data['video_url']
                    elif 'download_url' in video_data:
                        video_url = video_data['download_url']

                    if not video_url:
                        # download_contentを使用（60秒タイムアウト）
                        app.logger.info(f'[DEBUG] Using download_content method...')
                        content = client.videos.download_content(video_id, variant='video')
                        content.write_to_file(str(video_path))
                    else:
                        # URLから直接ダウンロード
                        app.logger.info(f'[DEBUG] Downloading from URL: {video_url[:50]}...')
                        response = requests.get(video_url, timeout=60, stream=True)
                        response.raise_for_status()

                        with open(video_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)

                    app.logger.info(f'[DEBUG] Download completed: {video_path}')
                except requests.Timeout:
                    app.logger.error(f'[ERROR] Download timeout after 60 seconds')
                    return jsonify({'error': 'ダウンロードがタイムアウトしました（60秒）。ネットワークを確認してください。'}), 500
                except Exception as e:
                    app.logger.error(f'[ERROR] Download failed: {str(e)}', exc_info=True)
                    return jsonify({'error': f'ダウンロードエラー: {str(e)}'}), 500
            else:
                app.logger.info(f'[DEBUG] File already exists: {video_path}')

            # ダウンロード済みでも、最終フレームが未作成なら抽出を実行
            if not last_frame_path.exists():
                ok = extract_last_frame(video_path, last_frame_path)
                if not ok:
                    app.logger.error('最終フレーム抽出が両方の方法で失敗しました。')
            else:
                app.logger.info(f'[DEBUG] Last frame already exists: {last_frame_path}')

            return jsonify({
                'status': 'completed',
                'video_path': f'/video/{video_id}',
                'progress': getattr(video, 'progress', 100)
            })
        elif video.status == 'failed':
            error_msg = getattr(getattr(video, 'error', None), 'message', 'ビデオ生成に失敗しました')
            app.logger.error(f'[ERROR] Video generation failed: {error_msg}')
            return jsonify({'status': 'failed', 'error': error_msg})
        else:
            return jsonify({
                'status': video.status,
                'progress': getattr(video, 'progress', 0)
            })
    except Exception as e:
        app.logger.error(f'[ERROR] Exception in check_status: {str(e)}', exc_info=True)
        return jsonify({'error': f'ステータス確認エラー: {str(e)}'}), 500

@app.route('/video/<video_id>')
def get_video(video_id):
    video_path = static_dir / f'{video_id}.mp4'
    if video_path.exists():
        app.logger.info(f'[DEBUG] Serving video: {video_path}')
        return send_file(video_path, mimetype='video/mp4')
    app.logger.warning(f'ビデオが見つかりません: {video_path}')
    return 'ビデオが見つかりません', 404

@app.route('/open-folder')
def open_folder():
    import subprocess
    subprocess.run(['open', str(static_dir.absolute())])
    app.logger.info(f'[DEBUG] Opened folder: {static_dir.absolute()}')
    return jsonify({'status': 'ok'})

@app.route('/list-last-frames')
def list_last_frames():
    # PNG のみを返却。新しい順。正規ファイル名のみ（video_で始まるもの）を対象
    files = [p for p in static_dir.glob('*_last_frame.png') if p.name.startswith('video_')]
    files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
    last_frames = [f'/static/{p.name}' for p in files]
    app.logger.info(f'[DEBUG] Available last frames: {last_frames}')
    resp = make_response(jsonify({'last_frames': last_frames}))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/reextract/<video_id>')
def reextract(video_id: str):
    """手動で最終フレーム抽出をやり直すためのデバッグ用エンドポイント。"""
    video_path = static_dir / f'{video_id}.mp4'
    last_frame_path = static_dir / f'{video_id}_last_frame.png'
    if not video_path.exists():
        return jsonify({'ok': False, 'error': 'mp4 not found', 'video_id': video_id}), 404
    ok = extract_last_frame(video_path, last_frame_path)
    return jsonify({'ok': ok, 'last_frame': f'/static/{last_frame_path.name}', 'video_id': video_id})

if __name__ == '__main__':
    # デバッグモードを無効化して、安定したログ出力を目指します。
    app.run(debug=False, host='0.0.0.0', port=5001)

