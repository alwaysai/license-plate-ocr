import time
import edgeiq
import easyocr

"""
Use object detection to detect and read automotive license plates in the frame in realtime.

To change the computer vision model, follow this guide:
https://dashboard.alwaysai.co/docs/application_development/changing_the_model.html

To change the engine and accelerator, follow this guide:
https://dashboard.alwaysai.co/docs/application_development/changing_the_engine_and_accelerator.html
"""


def main():
    # The current frame index
    frame_idx = 0
    # The number of frames to skip before running detector
    detect_period = 30

    # Load the object detection model
    obj_detect = edgeiq.ObjectDetection(
        "alwaysai/vehicle_license_mobilenet_ssd")
    obj_detect.load(engine=edgeiq.Engine.DNN)

    # Load the tracker to reduce tracking burden
    tracker = edgeiq.CorrelationTracker(max_objects=5)
    fps = edgeiq.FPS()

    # Load the OCR reader
    reader = easyocr.Reader(['en'], gpu=False)

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

                    # if using new detections, update 'predictions'
                    if frame_idx % detect_period == 0:
                        results = obj_detect.detect_objects(
                            frame, confidence_level=.5)
                        frame = edgeiq.markup_image(
                            frame, results.predictions, colors=obj_detect.colors)

                        # Generate text to display on streamer
                        text = ["Model: {}".format(obj_detect.model_id)]
                        text.append(
                            "Inference time: {:1.3f} s".format(results.duration))
                        text.append("Objects:")

                        # Stop tracking old objects
                        if tracker.count:
                            tracker.stop_all()

                        predictions = results.predictions

                        # use 'number' to identify unique objects
                        number = 0
                        for prediction in predictions:
                            number = number + 1
                            text.append("{}_{}: {:2.2f}%".format(
                                prediction.label, number, prediction.confidence * 100))
                            tracker.start(frame, prediction)

                            if(prediction.label == "license_plate"):
                                license_image = edgeiq.cutout_image(
                                    frame, prediction.box)

                                try:
                                    output = reader.readtext(
                                        license_image, detail=0)
                                    print(f'{prediction.label}_{number}: {output}')
                                    text.append('{}_{} reads: {}'.format(prediction.label, number, output))

                                except Exception as e:
                                    print(
                                        f'app.py: Error processing image through OCR lib: ERROR: {e}')

                            tracker.start(frame, prediction)

                    else:
                        # otherwise, set 'predictions' to the tracked predictions
                        if tracker.count:
                            predictions = tracker.update(frame)

                    # either way, use 'predictions' to mark up the image and update text
                    frame = edgeiq.markup_image(
                        frame, predictions, show_labels=True,
                        show_confidences=False, colors=obj_detect.colors)

                    streamer.send_data(frame, text)
                    frame_idx += 1

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
