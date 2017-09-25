import logging
import subprocess
import os

from concreate.builder import Builder
from concreate.errors import ConcreateError


logger = logging.getLogger('concreate')


class DockerBuilder(Builder):
    """This class wraps docker build command to build and image"""

    def build(self, build_args):
        """After the source siles are generated, the container image can be built.
        We're using Docker to build the image currently.

        This can be changed by specifying the tags in CLI using --build-tags option.

        Args:
          build_tags - a list of image tags
        """
        tags = build_args.build_tags
        cmd = ["docker", "build"]

        # Custom tags for the container image
        logger.debug("Custom tags for container image specified: %s" %
                     ", ".join(tags))

        for tag in tags:
            cmd.extend(["-t", tag])

        logger.info("Building container image...")

        cmd.append(os.path.join(self.target, 'image'))

        logger.debug("Running Docker build: '%s'" % " ".join(cmd))

        try:
            subprocess.check_call(cmd)

            logger.info("Image built and available under following tags: %s"
                        % ", ".join(tags))
        except:
            raise ConcreateError("Image build failed, see logs above.")