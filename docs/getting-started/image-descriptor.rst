Preparing image descriptor
============================

This section will guide you through a very simple example.

1. Using a standard text editor create an empty ``image.yaml`` file. It is recommended to use the ``image.yaml`` naming scheme.
2. As described in :doc:`Image Descriptor </descriptor/index>` several values are mandatory. Add the following to the file:

.. code-block:: yaml

   name: my-example
   version: 1.0
   from: centos:7

* Next, while optional, it is recommended to add a suitable ``description`` tag e.g.

.. code-block:: yaml

    description: My Example Tomcat Image

While this configuration will build in CEKit it isn't very interesting as it will simply create another image layered on top of CentOS 7. The descriptor should now look like:

.. code-block:: yaml
   :caption: image.yaml

    name: my-example
    version: 1.0
    from: centos:7
    description: My Example Tomcat Image


It is possible to directly add further content to the image at this point through a variety of methods. Labels, ports, packages etc can be used - see :doc:`here </descriptor/image>`. In general modules are used as the 'building blocks' to assemble the image - they can be used as individual libraries or shared blocks across multiple images. So, move onto to :doc:`modules </getting-started/modules>` to discover more about these.
