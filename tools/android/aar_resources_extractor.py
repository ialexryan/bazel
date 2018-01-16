# pylint: disable=g-direct-third-party-import
# Copyright 2017 The Bazel Authors. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""A tool for extracting resource files from an AAR.

An AAR may contain resources under the /res directory. This tool extracts all
of the resources into a directory. If no resources exist, it creates an
empty.xml file that defines no resources.

In the future, this script may be extended to also extract assets.
"""

import os
import sys
import zipfile

from tools.android import junction
from third_party.py import gflags

FLAGS = gflags.FLAGS

gflags.DEFINE_string("input_aar", None, "Input AAR")
gflags.MarkFlagAsRequired("input_aar")
gflags.DEFINE_string("output_res_dir", None, "Output resources directory")
gflags.MarkFlagAsRequired("output_res_dir")
gflags.DEFINE_string("output_assets_dir", None, "Output assets directory")


def ExtractResources(aar, output_res_dir):
  """Extract resource from an `aar` file to the `output_res_dir` directory."""
  aar_contains_no_resources = True
  output_res_dir_abs = os.path.abspath(output_res_dir)
  for name in aar.namelist():
    if name.startswith("res/"):
      ExtractOneFile(aar, name, output_res_dir_abs)
      aar_contains_no_resources = False
  if aar_contains_no_resources:
    empty_xml_filename = output_res_dir + "/res/values/empty.xml"
    WriteFileWithJunctions(empty_xml_filename, b"<resources/>")


def ExtractAssets(aar, output_assets_dir):
  """Extracts assets from an `aar` file to the `output_assets_dir` directory."""
  aar_contains_no_assets = True
  output_assets_dir_abs = os.path.abspath(output_assets_dir)
  for name in aar.namelist():
    if name.startswith("assets/"):
      ExtractOneFile(aar, name, output_assets_dir_abs)
      aar_contains_no_assets = False
  if aar_contains_no_assets:
    # aapt will ignore this file and not print an error message, because it
    # thinks that it is a swap file. We need to create at least one file so that
    # Bazel does not complain that the output tree artifact was not created.
    empty_asset_filename = (output_assets_dir +
                            "/assets/empty_asset_generated_by_bazel~")
    WriteFileWithJunctions(empty_asset_filename, b"")


def WriteFileWithJunctions(filename, content):
  """Writes file including creating any junctions or directories necessary."""
  if os.name == "nt":
    # Create a junction to the parent directory, because its path might be too
    # long. Creating the junction also creates all parent directories.
    with junction.TempJunction(os.path.dirname(filename)) as junc:
      filename = os.path.join(junc, os.path.basename(filename))
  else:
    os.makedirs(os.path.dirname(filename))
  with open(filename, "wb") as openfile:
    openfile.write(content)


def ExtractOneFile(aar, name, abs_output_dir):
  """Extract one file from the aar to the output directory."""
  if os.name == "nt":
    fullpath = os.path.normpath(os.path.join(abs_output_dir, name))
    if name[-1] == "/":
      # The zip entry is a directory. Create a junction to it, which also
      # takes care of creating the directory and all of its parents in a
      # longpath-safe manner.
      # We must pretend to have extracted this directory, even if it's
      # empty, therefore we mustn't rely on creating it as a parent
      # directory of a subsequently extracted zip entry (because there may
      # be no such subsequent entry).
      with junction.TempJunction(fullpath.rstrip("/")) as juncpath:
        pass
    else:
      # The zip entry is a file. Create a junction to its parent directory,
      # then open the compressed entry as a file object, so we can extract
      # the data even if the extracted file's path would be too long.
      # The tradeoff is that we lose the permission bits of the compressed
      # file, but Unix permissions don't mean much on Windows anyway.
      with junction.TempJunction(os.path.dirname(fullpath)) as juncpath:
        extracted_path = os.path.join(juncpath, os.path.basename(fullpath))
        with aar.open(name) as src_fd:
          with open(extracted_path, "wb") as dest_fd:
            dest_fd.write(src_fd.read())
  else:
    aar.extract(name, abs_output_dir)


def main():
  with zipfile.ZipFile(FLAGS.input_aar, "r") as aar:
    ExtractResources(aar, FLAGS.output_res_dir)
    if FLAGS.output_assets_dir is not None:
      ExtractAssets(aar, FLAGS.output_assets_dir)

if __name__ == "__main__":
  FLAGS(sys.argv)
  main()
