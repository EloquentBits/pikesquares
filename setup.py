# encoding: utf-8

import sys
import subprocess
import os

import errno
import shlex

import setuptools
from setuptools.dist import Distribution
from setuptools.command.build import build
from setuptools.command.build_ext import build_ext
from setuptools.command.build_py import build_py
from setuptools.command.install import install
from setuptools.command.install_lib import install_lib

#from distutils.core import Extension

# local script imports:
sys.path.insert(0, os.path.dirname(__file__))

print(sys.path)

#import uwsgiconfig as uc
import uwsgiconfig

from wheel.bdist_wheel import bdist_wheel

#from setuptools import setup, find_packages, Extension
import pathlib
import shutil

#import pkgconfig
#import platform

suffix = '.pyd' if os.name == 'nt' else '.so'

class CustomExtension(setuptools.Extension):
    def __init__(self, path):
        self.path = path
        super().__init__(pathlib.PurePath(path).name, [])

class build_CustomExtensions(build_ext):
    def run(self):
        for ext in (x for x in self.extensions if isinstance(x, CustomExtension)):
            source = f"{ext.path}{suffix}"
            build_dir = pathlib.PurePath(self.get_ext_fullpath(ext.name)).parent
            os.makedirs(f"{build_dir}/{pathlib.PurePath(ext.path).parent}",
                exist_ok = True)
            print(f"copy from: {source=} to: {build_dir}/{source}")
            shutil.copy(f"{source}", f"{build_dir}/{source}")

def find_extensions(directory):
    extensions = []
    for path, _, filenames in os.walk(directory):
        for filename in filenames:
            filename = pathlib.PurePath(filename)
            if pathlib.PurePath(filename).suffix == suffix:
                extensions.append(CustomExtension(os.path.join(path, filename.stem)))
    print(f"{extensions=}")
    return extensions


class PikeSquaresBuildPyCommand(build_py):
    """Custom build command."""

    def run(self):
        #subprocess.run(['sh', 'pyuwsgi_pre_build.sh'], check=True)
        #subprocess.run(['python', 'scripts/my_custom_script.py'], check=True)
        #subprocess.run(['sh', 'pyzmq_tools/install_libzmq.sh'], check=True)

        setuptools.command.build_py.build_py.run(self)

uwsgi_compiled = False

def get_profile():
    is_pypy = False
    try:
        import __pypy__  # NOQA
        is_pypy = True
    except ImportError:
        pass
    if is_pypy:
        profile = os.environ.get('UWSGI_PROFILE', 'buildconf/pypy.ini')
    else:
        profile = os.environ.get('UWSGI_PROFILE', 'buildconf/default.ini')
    if not profile.endswith('.ini'):
        profile = "%s.ini" % profile
    if '/' not in profile:
        profile = "buildconf/%s" % profile

    return profile

#def patch_bin_path(cmd, conf):

#    bin_name = conf.get('bin_name')

#    if not os.path.isabs(bin_name):
#        print('PATCHING "bin_name" to properly install_scripts dir')
#        print(f"{cmd.install_scripts=}")

#        print(f"{os.path.join(cmd.install_scripts, conf.get('bin_name'))=}")
#        try:
#            if not os.path.exists(cmd.install_scripts):
#                os.makedirs(cmd.install_scripts)
#            conf.set('bin_name',
#                     os.path.join(cmd.install_scripts, conf.get('bin_name')))
#        except Exception:
#            conf.set('bin_name', sys.prefix + '/bin/' + bin_name)


#class uWSGIBuilder(build_ext):

#    def run(self):
#        global uwsgi_compiled
#        if not uwsgi_compiled:
#            conf = uc.uConf(get_profile())
#            patch_bin_path(self, conf)
#            uc.build_uwsgi(conf)
#            uwsgi_compiled = True

#class uWSGIInstall(install):

#    def run(self):
#        print("===================== install")
#        global uwsgi_compiled
#        if not uwsgi_compiled:
#            conf = uc.uConf(get_profile())
#            patch_bin_path(self, conf)
#            uc.build_uwsgi(conf)
#            uwsgi_compiled = True
#        install.run(self)


#class uWSGIInstallLib(install_lib):

#    def run(self):
#        print("===================== install_lib")
#        global uwsgi_compiled
#        if not uwsgi_compiled:
#            conf = uc.uConf(get_profile())
#            patch_bin_path(self, conf)
#            uc.build_uwsgi(conf)
#            uwsgi_compiled = True
#        install_lib.run(self)



class uWSGIBuildExt(build_ext):

    UWSGI_NAME = 'pyuwsgi'
    UWSGI_PLUGIN = 'pyuwsgi'
    UWSGI_PROFILE = 'pikesquares'

    SHARED_LIBS = [
        'libzmq',
        'openssl',
        'sqlite3',
    ]
    #if platform.system() == "Linux":
    #    SHARED_LIBS += ['avahi-client']

    def build_extensions(self):
        self.uwsgi_setup()
        # XXX: needs uwsgiconfig fix
        self.uwsgi_build()
        if 'UWSGI_USE_DISTUTILS' not in os.environ:
            # XXX: needs uwsgiconfig fix
            # uwsgiconfig.build_uwsgi(self.uwsgi_config)
            return

        else:
            # XXX: needs uwsgiconfig fix
            os.unlink(self.uwsgi_config.get('bin_name'))

        # FIXME: else build fails :(
        for baddie in set(self.compiler.compiler_so) & set(('-Wstrict-prototypes',)):
            self.compiler.compiler_so.remove(baddie)

        build_ext.build_extensions(self)

    def uwsgi_setup(self):
        profile = os.environ.get('UWSGI_PROFILE') or 'buildconf/%s.ini' % self.UWSGI_PROFILE

        if not profile.endswith('.ini'):
            profile = profile + '.ini'
        if '/' not in profile:
            profile = 'buildconf/' + profile

        # FIXME: update uwsgiconfig to properly set _EVERYTHING_!
        config = uwsgiconfig.uConf(profile)

        # insert in the beginning so UWSGI_PYTHON_NOLIB is exported
        # before the python plugin compiles
        ep = [p.strip() for p in config.get('embedded_plugins').split(',')]
        if self.UWSGI_PLUGIN in ep:
            ep.remove(self.UWSGI_PLUGIN)
        ep.insert(0, self.UWSGI_PLUGIN)
        # Remove domain plugin depends on user OS
        #ep.remove('bonjour' if platform.system() == "Linux" else 'avahi')
        #config.set('libs', ",".join([
        #    pkgconfig.libs(lib) for lib in self.SHARED_LIBS
        #]))
        #config.set('cflags', ",".join([
        #    pkgconfig.cflags(c) for c in self.SHARED_LIBS
        #]))
        config.set('embedded_plugins', ','.join(ep))
        config.set('as_shared_library', 'true')
        config.set('bin_name', self.get_ext_fullpath(self.UWSGI_NAME))
        print(f"{self.get_ext_fullpath(self.UWSGI_NAME)=}")
        try:
            os.makedirs(os.path.dirname(config.get('bin_name')))
            print(f"{os.path.dirname(config.get('bin_name'))=}")
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        self.uwsgi_profile = profile
        self.uwsgi_config = config

    def uwsgi_build(self):
        print("=====uwsgi_build=======")
        uwsgiconfig.build_uwsgi(self.uwsgi_config)
        print(f"{self.extensions=}")

        # XXX: merge uwsgi_setup (see other comments)
        for ext in self.extensions:
            if ext.name == self.UWSGI_NAME:
                ext.sources = [s + '.c' for s in self.uwsgi_config.gcc_list]
                ext.library_dirs = self.uwsgi_config.include_path[:]
                ext.libraries = list()
                ext.extra_compile_args = list()

                for x in uwsgiconfig.uniq_warnings(
                    self.uwsgi_config.ldflags + self.uwsgi_config.libs,
                ):
                    for y in shlex.split(x):
                        if y.startswith('-l'):
                            ext.libraries.append(y[2:])
                        elif y.startswith('-L'):
                            ext.library_dirs.append(y[2:])

                for x in self.uwsgi_config.cflags:
                    for y in shlex.split(x):
                        if y:
                            ext.extra_compile_args.append(y)

            #elif ext.name == "hiredis":
                # build hiredis
            #    ext.sources = ["/usr/local/src/hiredis-1.1.0/*",]
            #    ext.library_dirs = ["/usr/local/include/hiredis",]
            #    ext.libraries = ["hiredis",]
            # with open("exception", 'w') as file:
            os.system(f"echo '[pikesquares setup.py] {ext.libraries=}\n[pikesquares setup.py] {ext.library_dirs=}\n[pikesquares setup.py] {ext.extra_compile_args=}'")

    #def run(self):
    #    for ext in (x for x in self.extensions if isinstance(x, CustomExtension)):
    #        source = f"{ext.path}{suffix}"
    #        build_dir = pathlib.PurePath(self.get_ext_fullpath(ext.name)).parent
    #        os.makedirs(f"{build_dir}/{pathlib.PurePath(ext.path).parent}",
                         #            exist_ok = True)
    #        print(f"copy from: {source=} to: {build_dir}/{source}")
    #        shutil.copy(f"{source}", f"{build_dir}/{source}")



class uWSGIWheel(bdist_wheel):
    def finalize_options(self):
        print("===================== uWSGIWheel.finalize_options")
        bdist_wheel.finalize_options(self)
        self.root_is_pure = False

class uWSGIBuildCmd(build):
    def initialize_options(self):
        import distutils
        distutils.command.build.build.initialize_options(self)
        self.build_base = '_build'


class uWSGIDistribution(Distribution):

    def __init__(self, *attrs):
        print("===================== uWSGIDistribution.__init__")
        Distribution.__init__(self, *attrs)
        #self.cmdclass['install'] = uWSGIInstall
        #self.cmdclass['install_lib'] = uWSGIInstallLib
        self.cmdclass['build_ext'] = uWSGIBuildExt
        self.cmdclass['build'] = uWSGIBuildCmd
        #self.cmdclass['build_py'] = PikeSquaresBuildPyCommand
        #self.cmdclass['bdist_wheel'] = uWSGIWheel

    #def iter_distribution_names(self):
    #    for pkg in self.packages or ():
    #        yield pkg
    #    for module in self.py_modules or ():
    #        yield module

    def has_ext_modules(self):
        return True

    def is_pure(self):
        return False


setuptools.setup(
    name='pikesquares-binary',
    author='Eloquent Bits Inc',
    author_email='philip.kalinsky@eloquentbits.com',
    url='',
    python_requires=">=3.11",
    distclass = uWSGIDistribution,


    #cmdclass={
    #    'build_ext': uWSGIBuildExt,
    #    'bdist_wheel': uWSGIWheel,
    #},

    #packages = ["vconf-binary"],

    #package_data = {
    #    "vconf-binary": [
    #        "extensions/libhiredis.so"
    #    ]
    #},
    #include_package_data=True,
    #has_ext_modules=lambda: True,

    py_modules=[
        'uwsgidecorators',
    ],
    ext_modules=[
        setuptools.Extension(
            'pyuwsgi', 
            sources=[]
        ),
        #setuptools.Extension('hiredis', sources=[]),
    ],

    #ext_modules = find_extensions("extensions"),

    #data_files=[
    #    (
    #      'vconf/resources',
    #      [
    #          'vconf-resources/vconf.so', 
    #          'vconf-resources/bootstrap_pex.py'
    #        ]
    #    )
    #],

    #package_data={
    #    "mypkg": ["*.txt"],
    #    "mypkg.data": ["*.rst"],
    #}


    #install_requires=[
    #    'platformdirs',
        #'twitter.common.contextutil',
    #],

    #ext_modules=[
    #    Extension('vconf', sources=[]),
    #    ] + extensions,

    #entry_points={
        #'console_scripts': ['vconf=vconf:run', ],
    #    'console_scripts': [
    #        'vconf=vconf_main:run'
    #    ],
    #},

    classifiers=[
        'Development Status :: 5 - Production/Stable',
        "Environment :: Web Environment",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.11",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: PikeSquares",
        "Topic :: Internet :: WWW/HTTP :: PikeSquares :: Server",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        ]
    )

"""
https://stackoverflow.com/a/63436907

from setuptools import setup, find_packages, Extension
from setuptools.command.build_ext import build_ext
import os
import pathlib
import shutil

suffix = '.pyd' if os.name == 'nt' else '.so'

class CustomDistribution(Distribution):
  def iter_distribution_names(self):
    for pkg in self.packages or ():
      yield pkg
    for module in self.py_modules or ():
      yield module

class CustomExtension(Extension):
  def __init__(self, path):
    self.path = path
    super().__init__(pathlib.PurePath(path).name, [])

class build_CustomExtensions(build_ext):
  def run(self):
    for ext in (x for x in self.extensions if isinstance(x, CustomExtension)):
      source = f"{ext.path}{suffix}"
      build_dir = pathlib.PurePath(self.get_ext_fullpath(ext.name)).parent
      os.makedirs(f"{build_dir}/{pathlib.PurePath(ext.path).parent}",
          exist_ok = True)
      shutil.copy(f"{source}", f"{build_dir}/{source}")

def find_extensions(directory):
  extensions = []
  for path, _, filenames in os.walk(directory):
    for filename in filenames:
      filename = pathlib.PurePath(filename)
      if pathlib.PurePath(filename).suffix == suffix:
        extensions.append(CustomExtension(os.path.join(path, filename.stem)))
  return extensions

setup(
  # Stuff
  ext_modules = find_extensions("PackageRoot"),
  cmdclass = {'build_ext': build_CustomExtensions}
  distclass = CustomDistribution
)
"""
