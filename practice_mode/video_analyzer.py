import cv2
import mediapipe as mp
import threading
import numpy as np
import math



class VideoAnalyzer:


    def __init__(self):

        self.running = False

        self.total_frames = 0
        self.face_frames = 0
        self.eye_frames = 0
        self.capture_error = None
        self.capture_device = None


        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )


    def start(self):
        self.total_frames = 0
        self.face_frames = 0
        self.eye_frames = 0
        self.capture_error = None
        self.capture_device = cv2.VideoCapture(0)
        if not self.capture_device.isOpened():
            self.capture_device.release()
            self.capture_device = None
            raise RuntimeError("Camera could not be opened. Check camera permissions and availability.")
        ok, _ = self.capture_device.read()
        if not ok:
            self.capture_device.release()
            self.capture_device = None
            raise RuntimeError("Camera opened but returned no video frame.")

        self.running = True
        self.thread = threading.Thread(target=self.capture, daemon=True)
        self.thread.start()



    def capture(self):

        cap = self.capture_device
        try:
            while self.running:
                success, frame = cap.read()
                if not success:
                    self.capture_error = "Camera stopped returning frames."
                    break


                self.total_frames += 1


                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


                result = self.face_mesh.process(rgb)



                if result.multi_face_landmarks:

                    self.face_frames += 1


                    face = result.multi_face_landmarks[0]


                    if self.detect_eye_contact(face, frame.shape):

                        self.eye_frames += 1
        except Exception as exc:
            self.capture_error = f"Camera analysis failed: {exc}"
        finally:
            if cap is not None:
                cap.release()



    def detect_eye_contact(self, face, frame_shape):


        h,w,_ = frame_shape


        # 3D model points
        face_3d = np.array([
            [0,0,0],          # nose
            [0,-330,-65],     # chin
            [-225,170,-135],  # left eye
            [225,170,-135],   # right eye
            [-150,-150,-125], # left mouth
            [150,-150,-125]   # right mouth

        ], dtype=np.float64)



        landmarks = face.landmark


        face_2d = np.array([

            [
                landmarks[1].x*w,
                landmarks[1].y*h
            ],

            [
                landmarks[152].x*w,
                landmarks[152].y*h
            ],

            [
                landmarks[33].x*w,
                landmarks[33].y*h
            ],

            [
                landmarks[263].x*w,
                landmarks[263].y*h
            ],

            [
                landmarks[61].x*w,
                landmarks[61].y*h
            ],

            [
                landmarks[291].x*w,
                landmarks[291].y*h
            ]

        ], dtype=np.float64)



        focal_length = w

        center = (
            w/2,
            h/2
        )


        camera_matrix=np.array([

            [focal_length,0,center[0]],

            [0,focal_length,center[1]],

            [0,0,1]

        ])



        dist_coeffs=np.zeros((4,1))


        success, rotation_vec, translation_vec = cv2.solvePnP(

            face_3d,
            face_2d,
            camera_matrix,
            dist_coeffs

        )



        if not success:
            return False



        rotation_matrix,_ = cv2.Rodrigues(
            rotation_vec
        )


        angles=cv2.RQDecomp3x3(
            rotation_matrix
        )


        pitch = angles[0][0]
        yaw = angles[0][1]

        print(
        "Yaw:",
        round(yaw,2),
        "Pitch:",
        round(pitch,2)
        )


        # looking towards camera

        # calibrated for this webcam setup

        if (
            abs(yaw) < 15
            and
            (
                pitch < -160
                or
                pitch > 160
            )
        ):

            return True


        return False



    def stop(self):

        self.running=False


        if hasattr(self, "thread"):
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                raise RuntimeError("Camera capture did not stop cleanly.")
        if hasattr(self.face_mesh, "close"):
            self.face_mesh.close()



    def get_metrics(self):

        return {

            "total_frames":
            self.total_frames,


            "face_frames":
            self.face_frames,


            "eye_contact_frames":
            self.eye_frames

        }
