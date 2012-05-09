# Volatility
#
# Based on the source code from
# Volatools Basic
# Copyright (C) 2007 Komoku, Inc.
#
# Authors:
# Brendan Dolan-Gavitt <bdolangavitt@wesleyan.edu>
# Mike Auty <mike.auty@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
#
# The source code in this file was inspired by the excellent work of
# Brendan Dolan-Gavitt. Background information can be found in
# the following reference:
# "The VAD Tree: A Process-Eye View of Physical Memory," Brendan Dolan-Gavitt

import os.path
from volatility import plugin
from volatility.plugins.windows import common


class VADInfo(common.WinProcessFilter):
    """Dump the VAD info"""

    __name = "vadinfo"

    # Vad Protections. Also known as page protections. _MMVAD_FLAGS.Protection,
    # 3-bits, is an index into nt!MmProtectToValue (the following list).
    PROTECT_FLAGS = dict(enumerate([
        'PAGE_NOACCESS',
        'PAGE_READONLY',
        'PAGE_EXECUTE',
        'PAGE_EXECUTE_READ',
        'PAGE_READWRITE',
        'PAGE_WRITECOPY',
        'PAGE_EXECUTE_READWRITE',
        'PAGE_EXECUTE_WRITECOPY',
        'PAGE_NOACCESS',
        'PAGE_NOCACHE | PAGE_READONLY',
        'PAGE_NOCACHE | PAGE_EXECUTE',
        'PAGE_NOCACHE | PAGE_EXECUTE_READ',
        'PAGE_NOCACHE | PAGE_READWRITE',
        'PAGE_NOCACHE | PAGE_WRITECOPY',
        'PAGE_NOCACHE | PAGE_EXECUTE_READWRITE',
        'PAGE_NOCACHE | PAGE_EXECUTE_WRITECOPY',
        'PAGE_NOACCESS',
        'PAGE_GUARD | PAGE_READONLY',
        'PAGE_GUARD | PAGE_EXECUTE',
        'PAGE_GUARD | PAGE_EXECUTE_READ',
        'PAGE_GUARD | PAGE_READWRITE',
        'PAGE_GUARD | PAGE_WRITECOPY',
        'PAGE_GUARD | PAGE_EXECUTE_READWRITE',
        'PAGE_GUARD | PAGE_EXECUTE_WRITECOPY',
        'PAGE_NOACCESS',
        'PAGE_WRITECOMBINE | PAGE_READONLY',
        'PAGE_WRITECOMBINE | PAGE_EXECUTE',
        'PAGE_WRITECOMBINE | PAGE_EXECUTE_READ',
        'PAGE_WRITECOMBINE | PAGE_READWRITE',
        'PAGE_WRITECOMBINE | PAGE_WRITECOPY',
        'PAGE_WRITECOMBINE | PAGE_EXECUTE_READWRITE',
        'PAGE_WRITECOMBINE | PAGE_EXECUTE_WRITECOPY',
    ]))

    # Vad Types. The _MMVAD_SHORT.u.VadFlags (_MMVAD_FLAGS) struct on XP has
    # individual flags, 1-bit each, for these types. The _MMVAD_FLAGS for all
    # OS after XP has a member _MMVAD_FLAGS.VadType, 3-bits, which is an index
    # into the following enumeration.
    MI_VAD_TYPE = dict(enumerate([
        'VadNone',
        'VadDevicePhysicalMemory',
        'VadImageMap',
        'VadAwe',
        'VadWriteWatch',
        'VadLargePages',
        'VadRotatePhysical',
        'VadLargePageSection',
    ]))

    def render(self, outfd):
        for task in self.filter_processes():
            outfd.write("*" * 72 + "\n")
            outfd.write("Pid: {0:6}\n".format(task.UniqueProcessId))

            for vad in task.VadRoot.traverse():
                vad = vad.dereference()
                if vad and vad != 0:
                    try:
                        self.write_vad_short(outfd, vad)
                    except AttributeError: pass
                    try:
                        self.write_vad_control(outfd, vad)
                    except AttributeError: pass
                    try:
                        self.write_vad_ext(outfd, vad)
                    except AttributeError: pass

                outfd.write("\n")

    def write_vad_short(self, outfd, vad):
        """Renders a text version of a Short Vad"""
        outfd.write("VAD node @{0:08x} Start {1:08x} End {2:08x} Tag {3:4}\n".format(
            vad.obj_offset, vad.get_start(), vad.get_end(), vad.Tag))
        outfd.write("Flags: {0}\n".format(str(vad.u.VadFlags)))

        # although the numeric value of Protection is printed above with VadFlags,
        # let's show the user a human-readable translation of the protection
        outfd.write("Protection: {0}\n".format(
                self.PROTECT_FLAGS.get(vad.u.VadFlags.Protection.v(),
                                       hex(vad.u.VadFlags.Protection))))

        # translate the vad type if its available (> XP)
        if hasattr(vad.u.VadFlags, "VadType"):
            outfd.write("Vad Type: {0}\n".format(
                    self.MI_VAD_TYPE.get(vad.u.VadFlags.VadType.v(),
                                         hex(vad.u.VadFlags.VadType))))

    def write_vad_control(self, outfd, vad):
        """Renders a text version of a (non-short) Vad's control information"""
        # even if the ControlArea is not NULL, it is only meaningful
        # for shared (non private) memory sections.
        if vad.u.VadFlags.PrivateMemory == 1:
            return

        control_area = vad.ControlArea
        if not control_area:
            return

        outfd.write("ControlArea @{0:08x} Segment {1:08x}\n".format(
                control_area.dereference().obj_offset, control_area.Segment))

        outfd.write("Dereference list: Flink {0:08x}, Blink {1:08x}\n".format(
                control_area.DereferenceList.Flink,
                control_area.DereferenceList.Blink))

        outfd.write("NumberOfSectionReferences: {0:10} NumberOfPfnReferences:  "
                    "{1:10}\n".format(
                control_area.NumberOfSectionReferences,
                control_area.NumberOfPfnReferences))

        outfd.write("NumberOfMappedViews:       {0:10} NumberOfUserReferences: "
                    "{1:10}\n".format(
                control_area.NumberOfMappedViews,
                control_area.NumberOfUserReferences))

        outfd.write("WaitingForDeletion Event:  {0:08x}\n".format(
                control_area.WaitingForDeletion))

        outfd.write("Control Flags: {0}\n".format(str(control_area.u.Flags)))

        file_object = vad.ControlArea.FilePointer.dereference()
        if file_object and file_object != 0:
            outfd.write("FileObject @{0:08x} FileBuffer @ {1:08x}          , "
                        "Name: {2}\n".format(
                    file_object.obj_offset, file_object.FileName.Buffer,
                    file_object.FileName))

    def write_vad_ext(self, outfd, vad):
        """Renders a text version of a Long Vad"""
        if vad.obj_type != "_MMVAD_SHORT":
            outfd.write("First prototype PTE: {0:08x} Last contiguous PTE: "
                        "{1:08x}\n".format(
                    vad.FirstPrototypePte, vad.LastContiguousPte))

            outfd.write("Flags2: {0}\n".format(str(vad.u2.VadFlags2)))



class VADTree(VADInfo):
    """Walk the VAD tree and display in tree format"""

    __name = "vadtree"

    def render(self, outfd):
        for task in self.filter_processes():
            outfd.write(u"*" * 72 + "\n")
            outfd.write(u"Pid: {0:6}\n".format(task.UniqueProcessId))
            levels = {}
            for vad in task.VadRoot.traverse():
                vad = vad.dereference()
                if vad:
                    level = levels.get(vad.Parent.v(), -1) + 1
                    levels[vad.obj_offset] = level
                    outfd.write(u" " * level + u"{0:08x} - {1:08x}\n".format(
                                vad.get_start(),
                                vad.get_end()))

    def render_dot(self, outfd):
        for task in self.filter_processes():
            outfd.write(u"/" + "*" * 72 + "/\n")
            outfd.write(u"/* Pid: {0:6} */\n".format(task.UniqueProcessId))
            outfd.write(u"digraph processtree {\n")
            outfd.write(u"graph [rankdir = \"TB\"];\n")
            for vad in task.VadRoot.traverse():
                vad = vad.dereference()
                if vad:
                    if vad.Parent and vad.Parent.dereference():
                        outfd.write(u"vad_{0:08x} -> vad_{1:08x}\n".format(
                                vad.Parent.v() or 0, vad.obj_offset))

                    outfd.write(
                        u"vad_{0:08x} [label = \"{{ {1}\\n{2:08x} - {3:08x} }}\""
                        "shape = \"record\" color = \"blue\"];\n".format(
                            vad.obj_offset,
                            vad.Tag,
                            vad.get_start(),
                            vad.get_end()))

            outfd.write(u"}\n")


class VADWalk(VADInfo):
    """Walk the VAD tree"""

    __name = "vadwalk"

    def render(self, outfd):
        for task in self.filter_processes():
            outfd.write(u"*" * 72 + "\n")
            outfd.write(u"Pid: {0:6}\n".format(task.UniqueProcessId))
            outfd.write(u"{0:16s} {1:16s} {2:16s} {3:16s} {4:16s} {5:16s} {6:4}\n".format(
                    "Address", "Parent", "Left", "Right", "Start", "End", "Tag"))
            for vad in task.VadRoot.traverse():
                # Ignore Vads with bad tags (which we explicitly include as None)
                vad = vad.dereference()
                if vad:
                    outfd.write(u"{0:016x} {1:016x} {2:016x} {3:016x} {4:016x} {5:016x} {6:4}\n".format(
                        vad.obj_offset,
                        vad.Parent.v() or 0,
                        vad.LeftChild.dereference().obj_offset or 0,
                        vad.RightChild.dereference().obj_offset or 0,
                        vad.get_start(),
                        vad.get_end(),
                        vad.Tag))

class VADDump(VADInfo):
    """Dumps out the vad sections to a file"""

    __name = "vaddump"

    def __init__(self, dump_dir=None, verbose=False, **kwargs):
        """Dump all the memory reserved for a process in its vad tree.

        Args:
           dump_dir: Directory in which to dump the VAD files
           verbose: Print verbose progress information
        """
        super(VADDump, self).__init__(**kwargs)
        if self.session:
            dump_dir = dump_dir or self.session.dump_dir

        self.dump_dir = dump_dir
        if self.dump_dir is None:
            raise plugin.PluginError("Dump directory not specified.")

        if not os.path.isdir(self.dump_dir):
            debug.error(self.dump_dir + " is not a directory")

        self.verbose = verbose

    def render(self, outfd):
        for task in self.filter_processes():
            outfd.write("Pid: {0:6}\n".format(task.UniqueProcessId))
            # Get the task and all process specific information
            task_space = task.get_process_address_space()
            name = task.ImageFileName
            offset = task_space.vtop(task.obj_offset)
            if offset is None:
                outfd.write("Process does not have a valid address space.\n")
                continue

            outfd.write("*" * 72 + "\n")
            for vad in task.VadRoot.traverse():
                vad = vad.dereference()
                if not vad: continue

                # Ignore Vads with bad tags
                if vad.obj_type == "_MMVAD":
                    continue

                # Find the start and end range
                start = vad.get_start()
                end = vad.get_end()

                # Open the file and initialize the data
                path = os.path.join(
                    self.dump_dir, "{0}.{1:x}.{2:08x}-{3:08x}.dmp".format(
                        name, offset, start, end))

                with open(path, 'wb') as f:
                    # Copy the memory from the process's address space into the
                    # file. This will null pad any missing pages.
                    range_data = task_space.zread(start, end - start + 1)

                    if self.verbose:
                        outfd.write("Writing VAD for %s\n" % path)

                    f.write(range_data)