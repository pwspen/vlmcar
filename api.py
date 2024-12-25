import logging
import io
import time
import asyncio
from threading import Condition, Lock
from gpiozero import DistanceSensor
import RPi.GPIO as GPIO
from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder, Quality
from picamera2.outputs import FileOutput
import base64
from Motor import Motor

# Configure logging
# logging.basicConfig(
#     level=logging.DEBUG,
#     format='%(asctime)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.FileHandler('robot.log'),
#         logging.StreamHandler()
#     ]
# )
logger = logging.getLogger(__name__)

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()
        self.last_write_time = 0
        self.write_count = 0
        self.lock = Lock()

    def write(self, buf):
        try:
            with self.lock:
                self.write_count += 1
                current_time = time.time()
                
                if self.last_write_time:
                    time_diff = current_time - self.last_write_time
                    if time_diff > 1.0:
                        logger.warning(f"Long frame interval: {time_diff:.2f}s")
                
                self.last_write_time = current_time

            with self.condition:
                self.frame = buf
                self.condition.notify_all()
                
            # if self.write_count % 100 == 0:
            #     logger.debug(f"Frames written: {self.write_count}")
                
        except Exception as e:
            logger.error(f"Error in StreamingOutput.write: {e}")

class LocalRobot:
    def __init__(self):
        try:
            logger.info("Initializing LocalRobot...")
            
            # Initialize ultrasonic sensor
            try:
                self.sensor = DistanceSensor(echo=22, trigger=27, max_distance=3)
                logger.info("Ultrasonic sensor initialized")
            except Exception as e:
                logger.error(f"Failed to initialize ultrasonic sensor: {e}")
                raise
            
            # Initialize camera
            try:
                self.camera = Picamera2()
                self.camera.configure(self.camera.create_video_configuration(main={"size": (400, 300)}))
                self.output = StreamingOutput()
                self.encoder = JpegEncoder(q=90)
                self.camera.start_recording(self.encoder, FileOutput(self.output), quality=Quality.VERY_HIGH)
                logger.info("Camera initialized and recording started")
            except Exception as e:
                logger.error(f"Failed to initialize camera: {e}")
                raise
            
            # Initialize motor
            self.motor = Motor()
            logger.info("LocalRobot initialization complete")
            
        except Exception as e:
            logger.error(f"Failed to initialize LocalRobot: {e}")
            raise

    def get_current_frame(self, timeout=1.0) -> str:
        """Get the most recent camera frame
        Args:
            timeout (float): Maximum time to wait for a frame in seconds
            
        Returns:
            str | None: Base64 encoded image string or None if timeout
        """
        try:
            with self.output.condition:
                if self.output.condition.wait(timeout=timeout):
                    return base64.b64encode(self.output.frame).decode('utf-8')
                else:
                    logger.warning("Timeout waiting for frame")
                    return None
        except Exception as e:
            logger.error(f"Error getting frame: {e}")
            return None

    def get_distance(self) -> float:
        """Get the current distance reading from the ultrasonic sensor
        
        Returns:
            float: Distance in centimeters
        """
        try:
            return self.sensor.distance * 100
        except Exception as e:
            logger.error(f"Error getting distance: {e}")
            return None

    async def forward(self, duration=1.0):
        """Move forward for specified duration"""
        try:
            logger.debug("Moving forward")
            self.motor.setMotorModel(2000, 2000, 2000, 2000)
            await self.finish(duration)
        except Exception as e:
            logger.error(f"Error in forward movement: {e}")

    async def reverse(self, duration=1.0):
        """Move backward for specified duration"""
        try:
            logger.debug("Moving reverse")
            self.motor.setMotorModel(-2000, -2000, -2000, -2000)
            await self.finish(duration)
        except Exception as e:
            logger.error(f"Error in reverse movement: {e}")

    async def move_dist(self, dist):
        # 1s ~= 1m, so just route to forward or reverse directly
        if dist < 0:
            self.reverse(duration=dist)
        else:
            self.forward(duration=dist)

    async def rotate_right(self, duration=0.4):
        """Rotate right for specified duration"""
        try:
            logger.debug("Rotating right")
            self.motor.setMotorModel(2000, 2000, -2000, -2000)
            await self.finish(duration)
        except Exception as e:
            logger.error(f"Error in right rotation: {e}")

    async def rotate_left(self, duration=0.4):
        """Rotate left for specified duration"""
        try:
            logger.debug("Rotating left")
            self.motor.setMotorModel(-2000, -2000, 2000, 2000)
            await self.finish(duration)
        except Exception as e:
            logger.error(f"Error in left rotation: {e}")

    async def rotate_deg(self, degrees):
        """Negative is CCW, positive is CW"""
        rot_dur = degrees * (1.4/180) # 1.4s to go 180 deg
        if deg < 0:
            self.rotate_left(duration=rot_dur)
        else:
            self.rotate_right(duration=rot_dur)

    async def finish(self, dur):
        try:
            await asyncio.sleep(dur)
            self.motor.setMotorModel(0,0,0,0)
        except Exception as e:
            logger.error(f"Error in finish movement: {e}")

    def cleanup(self):
        """Clean up resources"""
        try:
            self.camera.stop_recording()
            self.motor.setMotorModel(0, 0, 0, 0)
            GPIO.cleanup()
            logger.info("Cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

if __name__ == "__main__":
    # 1.4s = 180deg
    # 0.7s = 90deg
    # both of the above are so close that it seems linear, let's try 20 deg
    # 0.1555s ~= 18 deg, so slight discount, but close enough!
    robot = LocalRobot()
    while True:
        asyncio.run(robot.rotate_right(duration=0.0777))
        asyncio.run(asyncio.sleep(1))
