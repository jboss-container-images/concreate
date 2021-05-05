Supported builder engines
================================

.. contents::
    :backlinks: none

CEKit supports following builder engines:

* :ref:`Docker builder <handbook/building/builder-engines:Docker builder>` -- builds the container image using `Docker <https://docs.docker.com/>`__
* :ref:`OSBS builder <handbook/building/builder-engines:OSBS builder>` -- builds the container image using `OSBS service <https://osbs.readthedocs.io>`__
* :ref:`Buildah builder <handbook/building/builder-engines:Buildah builder>` -- builds the container image using `Buildah <https://buildah.io/>`__
* :ref:`Podman builder <handbook/building/builder-engines:Podman builder>` -- builds the container image using `Podman <https://podman.io/>`__

Docker builder
---------------------------

This builder uses Docker daemon as the build engine. Interaction with Docker daemon is done via Python binding.

By default every image is squashed at the end of the build. This means that all layers above the base image
will be squashed into a single layer. You can disable it by using the ``--no-squash`` switch.

Input format
    Dockerfile
Parameters
    ``--pull``
        Ask a builder engine to check and fetch latest base image
    ``--tag``
        An image tag used to build image (can be specified multiple times)
    ``--no-squash``
        Do not squash the image after build is done.

Example
    Building Docker image

    .. code-block:: bash

        $ cekit build docker

Remote Docker daemon
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is possible to use environment variables to let CEKit know where is the Docker daemon
located it should connect to.

.. note::
    Read more about `Docker daemon settings related to exposing it to clients <https://docs.docker.com/engine/reference/commandline/dockerd/#daemon-socket-option>`__.

By default, if you do not specify anything, **CEKit will try to use a locally running Docker daemon**.

If you need to customize this behavior (for example when you want to use Docker daemon
running in a VM) you can set following environment variables: ``DOCKER_HOST``, ``DOCKER_TLS_VERIFY`` and
``DOCKER_CERT_PATH``. See section about :ref:`Docker environment variables <handbook/building/builder-engines:Docker environment variables>`
below for more information.

Docker environment variables
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``DOCKER_HOST``
    The ``DOCKER_HOST`` environment variable is where you specify where the Daemon is running. It supports
    multiple protocols, but the most widely used ones are: ``unix://`` (where you specify path to a local
    socket) and ``tcp://`` (where you can define host location and port).

    Examples of ``DOCKER_HOST``: ``unix:///var/run/docker.sock``, ``tcp://192.168.22.33:1234``.

    Depending how your daemon is configured you may need to configure settings related to encryption.

    .. code-block:: bash

        # Connect to a remote Docker daemon
        $ DOCKER_HOST="tcp://192.168.22.33:1234" cekit build docker
``DOCKER_TLS_VERIFY``
    You can set ``DOCKER_TLS_VERIFY`` to a non-empty value to indicate that the TLS verification should
    take place. By default certificate verification is **disabled**.
``DOCKER_CERT_PATH``
    You can point ``DOCKER_CERT_PATH`` environment variable to a directory containing certificates to use when
    connecting to the Docker daemon.
``DOCKER_TMPDIR``
    You can change the temporary directory used by Docker daemon by specifying the ``DOCKER_TMPDIR`` environment
    variable.

    .. note::
        Please note that this is environment variable **should be set on the daemon** and not on the client
        (CEKit command you execute). You need to modify your Docker daemon configuration and restart Docker
        to apply new value.

    By default it points to ``/var/lib/docker/tmp``. If you are short on space there, you may want to use
    a different directory. This temporary directory is used to generate the TAR file with the image that is
    later processed by the squash tool. If you have large images, make sure you have sufficient free space there.
``TMPDIR``
    This environment variable controls which directory should be used when a temporary directory is created
    by the CEKit tool. In case the default temporary directory location is low on space it may be required
    to point to a different location.

    One example when such change could be required is when the squash post-processing of the image is taking place
    and the default temporary directory location is low on space. Squashing requires to unpack the original
    image TAR file and apply transformation on it. This can be very storage-consuming process.

    You can read more on how this variable is used in the `Python docs <https://docs.python.org/3/library/tempfile.html#tempfile.gettempdir>`__.

    .. code-block:: bash

        $ TMPDIR="/mnt/external/tmp" cekit build docker
``DOCKER_TIMEOUT``
    By default it is set to ``600`` seconds.

    This environment variable is responsible for setting how long we will wait for the Docker
    daemon to return data. Sometimes, when the Docker daemon is busy and you have large images, it may be
    required to set this variable to some even higher number. Setting proper value is especially important
    when the squashing post-processing takes place because this is a very resource-consuming task and can
    take several minutes.

    .. code-block:: bash

        $ DOCKER_TIMEOUT="1000" cekit build docker

OSBS builder
---------------------------

This build engine is using ``rhpkg`` or ``fedpkg`` tool to build the image using OSBS service. By default
it performs **scratch build**. If you need a proper build you need to specify ``--release`` parameter.

By default every image is squashed at the end of the build. This means that all layers above the base image
will be squashed into a single layer.

.. note::
   URL based artifacts (See :ref:`here <descriptor/image:URL artifacts>`) will **not** be cached and instead will be added to ``fetch-artifacts.yaml`` to use the `OSBS integration <https://osbs.readthedocs.io/en/latest/users.html#fetch-artifacts-url-yaml>`_. This may be constrained by using :ref:`OSBS URL Restriction <handbook/configuration:OSBS URL Restriction>` configuration

.. note::
   Extra OSBS configuration may be passed in via the OSBS descriptor (See :ref:`here <descriptor/image:OSBS>`). Automatic `Cachito integration <https://osbs.readthedocs.io/en/latest/users.html#fetching-source-code-from-external-source-using-cachito>`_ may also be included within the :ref:`OSBS configuration <descriptor/image:OSBS configuration>` and if this is detected CEKit will include the commands in the Dockerfile.

Input format
    Dockerfile
Parameters
    ``--release``
        Perform an OSBS release build
    ``--user``
        Alternative user passed to build task
    ``--nowait``
        Do not wait for the task to finish
    ``--stage``
        Use stage environment
    ``--commit-message``
        Custom commit message for dist-git
    ``--sync-only``
        .. versionadded:: 3.4

        Generate files and sync with dist-git, but do not execute build
    ``--assume-yes``
        .. versionadded:: 3.4

        Run build in non-interactive mode answering all questions with 'Yes',
        useful for automation purposes

Example
    Performing scratch build

    .. code-block:: bash

        $ cekit build osbs

    Performing release build

    .. code-block:: bash

        $ cekit build osbs --release

Buildah builder
---------------------------

This build engine is using `Buildah <https://buildah.io>`_.

By default every image is squashed at the end of the build. This means that all layers (**including the base image**)
will be squashed into a single layer. You can disable it by using the ``--no-squash`` switch.

.. note::
   If you need to use any non default registry, please update ``/etc/containers/registry.conf`` file.

Input format
    Dockerfile
Parameters
    ``--pull``
        Ask a builder engine to check and fetch latest base image
    ``--tag``
        An image tag used to build image (can be specified multiple times)
    ``--no-squash``
        Do not squash the image after build is done.

Example
    Build image using Buildah

    .. code-block:: bash

        $ cekit build buildah

    Build image using Buildah and tag it as ``example/image:1.0``

    .. code-block:: bash

        $ cekit build buildah --tag example/image:1.0

Buildah environment variables
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``BUILDAH_LAYERS``
    The ``BUILDAH_LAYERS`` environment variable allows you to control whether the builder engine
    will cache intermediate layers during build.

    By default it is set to ``false``.

    You can enable it by setting the environment variable to ``true``. The initial build process will take
    longer because result of every command will need to be stored on the disk (commited), but
    subsequent builds (without any code change) should be faster because the layer cache will be
    reused.

    .. code-block:: bash

        $ BUILDAH_LAYERS="true" cekit build buildah

    .. warning::
        Caching layers conflicts with :doc:`multi-stage builds </handbook/multi-stage>`.
        A ticket was opened: https://bugzilla.redhat.com/show_bug.cgi?id=1746022. If you
        use multi-stage builds, make sure the ``BUILDAH_LAYERS`` environment variable
        is set to ``false``.

Podman builder
---------------------------

This build engine is using `Podman <https://podman.io>`_. Podman will perform non-privileged builds so
no special configuration is required.

By default every image is squashed at the end of the build. This means that all layers (**including the base image**)
will be squashed into a single layer. You can disable it by using the ``--no-squash`` switch.

Input format
    Dockerfile
Parameters
    ``--pull``
        Ask a builder engine to check and fetch latest base image
    ``--tag``
        An image tag used to build image (can be specified multiple times)
    ``--no-squash``
        Do not squash the image after build is done.

Example
    Build image using Podman

    .. code-block:: bash

        $ cekit build podman

    Build image using Podman

    .. code-block:: bash

        $ cekit build podman --pull

Podman environment variables
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``BUILDAH_LAYERS``
    .. note::
        Yes, the environment variable is called ``BUILDAH_LAYERS``, there is no typo. Podman uses
        Buildah code underneath.

    The ``BUILDAH_LAYERS`` environment variable allows you to control whether the builder engine
    will cache intermediate layers during build.

    By default it is set to ``true``.

    You can disable it by setting the environment variable to ``false``. This will make the build faster
    because there will be no need to commit result of every command. The downside of this setting
    is that you will not be able to leverage layer cache in subsequent builds.

    .. code-block:: bash

        $ BUILDAH_LAYERS="false" cekit build podman

    .. warning::
        Caching layers conflicts with :doc:`multi-stage builds </handbook/multi-stage>`.
        A ticket was opened: https://bugzilla.redhat.com/show_bug.cgi?id=1746022. If you
        use multi-stage builds, make sure the ``BUILDAH_LAYERS`` environment variable
        is set to ``false``.
