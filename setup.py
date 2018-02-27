from setuptools import setup

setup(
    name='pragma',
    version='0.1.0',
    packages=['pragma', 'pragma.core'],
    url='https://github.com/scnerd/pypragma',
    license='MIT',
    author='scnerd',
    author_email='scnerd@gmail.com',
    description='Python code transformers that mimic pragma compiler directives',
    long_description=open('README.rst').read(),
    install_requires=[
        'miniutils',
        'astor',
    ]
)
