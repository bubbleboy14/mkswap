from setuptools import setup

setup(
    name='mkswap',
    version="0.1",
    author='Mario Balibrera',
    author_email='mario.balibrera@gmail.com',
    license='MIT License',
    description='crypto bits',
    long_description='office and workers',
    packages=[
        'mkswap'
    ],
    zip_safe = False,
    install_requires = [
        "fyg >= 0.1.1",
        "rel >= 0.4.9.5",
        "websocket-client >= 1.7.0"
    ],
    entry_points = '''''',
    classifiers = [
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
)
