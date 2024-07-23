import time
import edgeiq
import easyocr
import os

"""
Use object detection to detect and read automotive license plates in the frame in realtime.

To change the computer vision model, follow this guide:
https://dashboard.alwaysai.co/docs/application_development/changing_the_model.html

To change the engine and accelerator, follow this guide:
https://docs.alwaysai.co/application_development/application_configuration.html#change-the-engine-and-accelerator
"""


def main():
    # Load the object detection model
    obj_detect = edgeiq.ObjectDetection(
        "alwaysai/vehicle_license_mobilenet_ssd")
    obj_detect.load(engine=edgeiq.Engine.DNN)

    # Load the tracker to reduce tracking burden
    tracker = edgeiq.CentroidTracker()
    fps = edgeiq.FPS()

    # Load the OCR reader
    reader = easyocr.Reader(
        ['en'],
        gpu=False,
        download_enabled=False,
        model_storage_directory='easy_ocr_model',
        user_network_directory=os.getcwd())

    # Console output
    print("Loaded model:\n{}\n".format(obj_detect.model_id))
    print("Engine: {}".format(obj_detect.engine))
    print("Accelerator: {}\n".format(obj_detect.accelerator))
    print("Labels:\n{}\n".format(obj_detect.labels))

    try:
        # Prepare to run detection on all the .mp4 videos in the video/ subfolder
        video_paths = edgeiq.list_files(
            base_path="./video/", valid_exts=".mp4")
        streamer = edgeiq.Streamer().setup()

        for video_path in video_paths:

            print(f'Playing video file: {video_path}')
            with edgeiq.FileVideoStream(video_path) \
                    as video_stream:

                # Allow Webcam to warm up
                time.sleep(2.0)
                fps.start()

                # loop detection
                while video_stream.more():
                    frame = video_stream.read()
                    predictions = []

                    results = obj_detect.detect_objects(
                        frame, confidence_level=.5)
                    frame = edgeiq.markup_image(
                        frame, results.predictions, colors=obj_detect.colors)

                    # Generate text to display on streamer
                    text = ["Model: {}".format(obj_detect.model_id)]
                    text.append(
                        "Inference time: {:1.3f} s".format(results.duration))
                    text.append("Objects:")

                    objects = tracker.update(results.predictions)

                    for (object_id, prediction) in objects.items():
                        text.append("{}_{}: {:2.2f}%".format(
                            prediction.label,
                            object_id,
                            prediction.confidence * 100))

                        if(prediction.label == "license_plate"):
                            license_image = edgeiq.cutout_image(
                                frame, prediction.box)

                            try:
                                output = reader.readtext(
                                    license_image, detail=0)
                                print(
                                    f'{prediction.label}_{object_id}: {output}'
                                    )
                                text.append('{}_{} reads: {}'.format(
                                    prediction.label, object_id, output))

                            except Exception as e:
                                print(
                                    f'app.py: Error processing image through OCR lib: ERROR: {e}')

                    # either way, use 'predictions' to mark up the image and update text
                    frame = edgeiq.markup_image(
                        frame, predictions, show_labels=True,
                        show_confidences=False, colors=obj_detect.colors)

                    streamer.send_data(frame, text)

                    fps.update()

                    if streamer.check_exit():
                        break
    finally:
        fps.stop()
        streamer.close()
        print("elapsed time: {:.2f}".format(fps.get_elapsed_seconds()))
        print("approx. FPS: {:.2f}".format(fps.compute_fps()))
        print("Program Ending")


if __name__ == "__main__":

    main()
