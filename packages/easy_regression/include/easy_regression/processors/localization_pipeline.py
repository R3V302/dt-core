import duckietown_code_utils as dtu
import rospy
from complete_image_pipeline.pipeline import run_pipeline

from easy_regression import ProcessorInterface, ProcessorUtilsInterface
from image_processing.more_utils import get_robot_camera_geometry_from_log

__all__ = [
    "LocalizationPipelineProcessor",
]

logger = dtu.logger


class LocalizationPipelineProcessor(ProcessorInterface):
    def __init__(self, line_detector: str, image_prep: str, lane_filter: str, anti_instagram: str):
        self.line_detector = line_detector
        self.image_prep = image_prep
        self.lane_filter = lane_filter
        self.anti_instagram = anti_instagram
        self.all_details = False

    def process_log(
        self, bag_in: dtu.BagReadProxy, prefix_in, bag_out, prefix_out, utils: ProcessorUtilsInterface
    ):
        log_name = utils.get_log().log_name

        vehicle_name = dtu.which_robot(bag_in)

        logger.info("Vehicle name: %s" % vehicle_name)

        # noinspection PyTypeChecker
        topic = dtu.get_image_topic(bag_in)

        rcg = get_robot_camera_geometry_from_log(bag_in)

        bgcolor = dtu.ColorConstants.BGR_DUCKIETOWN_YELLOW

        sequence = bag_in.read_messages_plus(topics=[topic])
        for _i, mp in enumerate(sequence):

            bgr = dtu.bgr_from_rgb(dtu.rgb_from_ros(mp.msg))

            res, stats = run_pipeline(
                bgr,
                gpg=rcg.gpg,
                rectifier=rcg.rectifier,
                line_detector_name=self.line_detector,
                image_prep_name=self.image_prep,
                lane_filter_name=self.lane_filter,
                anti_instagram_name=self.anti_instagram,
                all_details=self.all_details,
            )

            rect = (480, 640) if not self.all_details else (240, 320)
            res = dtu.resize_images_to_fit_in_rect(res, rect, bgcolor=bgcolor)

            dtu.logger.info(
                (
                    "abs: %s  window: %s  from log: %s"
                    % (mp.time_absolute, mp.time_window, mp.time_from_physical_log_start)
                )
            )
            headers = [
                "Robot: %s log: %s time: %.2f s" % (vehicle_name, log_name, mp.time_from_physical_log_start),
                "Algorithms | color correction: %s | preparation: %s | detector: %s | filter: %s"
                % (self.anti_instagram, self.image_prep, self.line_detector, self.lane_filter,),
            ]

            res = dtu.write_bgr_images_as_jpgs(res, dirname=None, bgcolor=bgcolor)

            cv_image = res["all"]

            for head in reversed(headers):
                max_height = 35
                cv_image = dtu.add_header_to_bgr(cv_image, head, max_height=max_height)

            otopic = "all"

            omsg = dtu.d8_compressed_image_from_cv_image(cv_image, same_timestamp_as=mp.msg)
            t = rospy.Time.from_sec(mp.time_absolute)
            dtu.logger.info(("written %r at t = %s" % (otopic, t.to_sec())))
            bag_out.write(prefix_out + "/" + otopic, omsg, t=t)

            for name, value in list(stats.items()):
                utils.write_stat(prefix_out + "/" + name, value, t=t)
