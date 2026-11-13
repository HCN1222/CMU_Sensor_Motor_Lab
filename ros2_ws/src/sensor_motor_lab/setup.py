from setuptools import find_packages, setup

package_name = 'sensor_motor_lab'
setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'pyserial'],
    zip_safe=True,
    maintainer='Lab Team',
    maintainer_email='lab-team@example.invalid',
    description='Arduino Uno serial bridge and rqt controls for four sensors and three motors',
    license='MIT',
    entry_points={'console_scripts': ['lab_bridge = sensor_motor_lab.bridge:main']},
)
