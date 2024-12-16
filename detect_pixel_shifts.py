import cv2
from dotenv import load_dotenv
import os
import threading
import queue
import subprocess

load_dotenv()

username = os.getenv('RTSP_USERNAME')
password = os.getenv('RTSP_PASSWORD')
hostname = os.getenv('RTSP_HOSTNAME')

rtsp_url = f"rtsp://{username}:{password}@{hostname}"
frame_queue = queue.Queue(maxsize=10)

def process_frames():
    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        print("Error: RTSP stream unavailable")
        exit(1)

    ret, prev_frame = cap.read()
    prev_grey_frame = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Unable to get frame")
            break

        grey_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        diff_frame = cv2.absdiff(grey_frame, prev_grey_frame)
        
        output_frame = diff_frame.copy()

        try:
            frame_queue.put(output_frame, block=False)
        except queue.Full:
            frame_queue.get()
            frame_queue.put(output_frame)


def stream_frames():
    ffmpeg_command = [
        "ffmpeg",
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "gray",
        "-s", "{}x{}".format(frame_width, frame_height),
        "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "ultrafast",
        "-f", "rtsp",
        "-rtsp_transport", "tcp",    # Explicitly use TCP
        "rtsp://localhost:8554/stream"
    ]

    ffmpeg_process = subprocess.Popen(
        ffmpeg_command,
        stdin=subprocess.PIPE
    )

    while True:
        try:
            frame = frame_queue.get()
            ffmpeg_process.stdin.write(frame.tobytes())
        except Exception as e:
            print(f"Error: {e}")
            break


if __name__ == "__main__":
    # Get stream properties
    cap = cv2.VideoCapture(rtsp_url)
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    cap.release()

    process_thread = threading.Thread(target=process_frames)
    stream_thread = threading.Thread(target=stream_frames)

    process_thread.start()
    stream_thread.start()

    try:
        process_thread.join()
        stream_thread.join()
    except KeyboardInterrupt:
        print("\nTerminating")
