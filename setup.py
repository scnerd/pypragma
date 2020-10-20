from setuptools import setup

setup(
    name='pragma',
    version='0.2.1',
    packages=['pragma', 'pragma.core', 'pragma.core.resolve'],
    url='https://github.com/scnerd/pypragma',
    license='MIT',
    author='scnerd',
    author_email='scnerd@gmail.com',
    description='Python code transformers that mimic pragma compiler directives',
    long_description=open('README.rst').read(),
    install_requires=[
        'miniutils',
        'astor',
        'nose'
    ]
)
