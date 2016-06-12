# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import fnmatch
from abc import abstractproperty
from hashlib import sha1
from os import sep as os_sep
from os.path import basename, join, normpath

import six
from twitter.common.collections.orderedset import OrderedSet

from pants.base.project_tree import Dir, File, Link
from pants.engine.selectors import Collection, Select, SelectDependencies, SelectProjection
from pants.source.wrapped_globs import Globs, RGlobs, ZGlobs
from pants.util.meta import AbstractClass
from pants.util.objects import datatype


class ReadLink(datatype('ReadLink', ['symbolic_path'])):
  """The result of reading a symbolic link."""

  def __new__(cls, path):
    return super(ReadLink, cls).__new__(cls, six.text_type(path))

  @property
  def path_globs(self):
    """Supports projecting the Path resulting from a ReadLink as a PathGlob.

    Because symlinks may be dead or point inside of other symlinks, it's necessary to resolve
    their components from the top of the buildroot.
    """
    return PathGlobs.create_from_specs('', [self.symbolic_path])


class Stats(datatype('Stats', ['dependencies'])):
  """A set of Stat objects."""

  def _filtered(self, cls):
    return tuple(s for s in self.dependencies if type(s) is cls)

  @property
  def files(self):
    return self._filtered(File)

  @property
  def dirs(self):
    return self._filtered(Dir)

  @property
  def links(self):
    return self._filtered(Link)


class FilteredPaths(datatype('FilteredPaths', ['paths'])):
  """A wrapper around a Paths object that has been filtered by some pattern."""


class FileContent(datatype('FileContent', ['path', 'content'])):
  """The content of a file, or None if it did not exist."""

  def __repr__(self):
    content_str = '(len:{})'.format(len(self.content)) if self.content is not None else 'None'
    return 'FileContent(path={}, content={})'.format(self.path, content_str)

  def __str__(self):
    return repr(self)


class FileDigest(datatype('FileDigest', ['path', 'digest'])):
  """A unique fingerprint for the content of a File."""


def _norm_with_dir(path):
  """Form of `normpath` that preserves a trailing slash-dot.

  In this case, a trailing slash-dot is used to explicitly indicate that a directory is
  being matched.

  TODO: No longer the case, AFAIK: could probably switch to just normpath.
  """
  normed = normpath(path)
  if path.endswith(os_sep + '.'):
    return normed + os_sep + '.'
  return normed


class Path(datatype('Path', ['path', 'stat'])):
  """A filesystem path, holding both its symbolic path name, and underlying canonical Stat.

  Both values are relative to the ProjectTree's buildroot.
  """


class Paths(datatype('Paths', ['dependencies'])):
  """A set of Path objects."""

  def _filtered(self, cls):
    return tuple(p for p in self.dependencies if type(p.stat) is cls)

  @property
  def files(self):
    return self._filtered(File)

  @property
  def dirs(self):
    return self._filtered(Dir)

  @property
  def links(self):
    return self._filtered(Link)

  @property
  def link_stats(self):
    return tuple(p.stat for p in self.links)


class PathGlob(AbstractClass):
  """A filename pattern.

  All PathGlob subclasses represent in-progress recursion that may match zero or more Stats. The
  leaves of a "tree" of PathGlobs will be Path objects which may or may not exist.
  """

  _DOUBLE = '**'
  _SINGLE = '*'

  @abstractproperty
  def canonical_stat(self):
    """A Dir relative to the ProjectTree, to which the remainder of this PathGlob is relative."""

  @abstractproperty
  def symbolic_path(self):
    """The symbolic name (specific to the execution of this PathGlob) for the canonical_stat."""

  @classmethod
  def create_from_spec(cls, canonical_stat, symbolic_path, filespec):
    """Given a filespec, return a PathGlob object.

    :param canonical_stat: A canonical Dir relative to the ProjectTree, to which the filespec
      is relative.
    :param symbolic_path: A symbolic name for the canonical_stat (or the same name, if no symlinks
      were traversed while expanding it).
    :param filespec: A filespec, relative to the canonical_stat.
    """
    if not isinstance(canonical_stat, Dir):
      raise ValueError('Expected a Dir as the canonical_stat. Got: {}'.format(canonical_stat))

    parts = _norm_with_dir(filespec).split(os_sep)
    if cls._DOUBLE in parts[0]:
      if parts[0] != cls._DOUBLE:
        raise ValueError(
            'Illegal component "{}" in filespec under {}: {}'.format(
              parts[0], symbolic_path, filespec))
      # There is a double-wildcard in a dirname of the path: double wildcards are recursive,
      # so there are two remainder possibilities: one with the double wildcard included, and the
      # other without.
      remainders = (join(*parts[1:]), join(*parts[0:]))
      return PathDirWildcard(canonical_stat, symbolic_path, parts[0], remainders)
    elif len(parts) == 1:
      # This is the path basename, and it may contain a single wildcard.
      return PathWildcard(canonical_stat, symbolic_path, parts[0])
    elif cls._SINGLE not in parts[0]:
      return PathLiteral(canonical_stat, symbolic_path, parts[0], join(*parts[1:]))
    else:
      # This is a path dirname, and it contains a wildcard.
      remainders = (join(*parts[1:]),)
      return PathDirWildcard(canonical_stat, symbolic_path, parts[0], remainders)


class PathWildcard(datatype('PathWildcard', ['canonical_stat', 'symbolic_path', 'wildcard']), PathGlob):
  """A PathGlob with a wildcard in the basename component."""


class PathLiteral(datatype('PathLiteral', ['canonical_stat', 'symbolic_path', 'literal', 'remainder']), PathGlob):
  """A PathGlob representing a partially-expanded literal Path.

  While it still requires recursion, a PathLiteral is simpler to execute than either `wildcard`
  type: it only needs to stat each directory on the way down, rather than listing them.

  TODO: Should be possible to merge with PathDirWildcard.
  """

  @property
  def directory(self):
    return join(self.canonical_stat.path, self.literal)


class PathDirWildcard(datatype('PathDirWildcard', ['canonical_stat', 'symbolic_path', 'wildcard', 'remainders']), PathGlob):
  """A PathGlob with a single or double-level wildcard in a directory name.

  Each remainders value is applied relative to each directory matched by the wildcard.
  """


class PathGlobs(datatype('PathGlobs', ['dependencies'])):
  """A set of 'PathGlob' objects.

  This class consumes the (somewhat hidden) support in FilesetWithSpec for normalizing
  globs/rglobs/zglobs into 'filespecs'.
  """

  @classmethod
  def create(cls, relative_to, files=None, globs=None, rglobs=None, zglobs=None):
    """Given various file patterns create a PathGlobs object (without using filesystem operations).

    :param relative_to: The path that all patterns are relative to (which will itself be relative
      to the buildroot).
    :param files: A list of relative file paths to include.
    :type files: list of string.
    :param string globs: A relative glob pattern of files to include.
    :param string rglobs: A relative recursive glob pattern of files to include.
    :param string zglobs: A relative zsh-style glob pattern of files to include.
    :param zglobs: A relative zsh-style glob pattern of files to include.
    :rtype: :class:`PathGlobs`
    """
    filespecs = OrderedSet()
    for specs, pattern_cls in ((files, Globs),
                               (globs, Globs),
                               (rglobs, RGlobs),
                               (zglobs, ZGlobs)):
      if not specs:
        continue
      res = pattern_cls.to_filespec(specs)
      excludes = res.get('excludes')
      if excludes:
        raise ValueError('Excludes not supported for PathGlobs. Got: {}'.format(excludes))
      new_specs = res.get('globs', None)
      if new_specs:
        filespecs.update(new_specs)
    return cls.create_from_specs(relative_to, filespecs)

  @classmethod
  def create_from_specs(cls, relative_to, filespecs):
    # TODO: We bootstrap the `canonical_stat` value here without validating that it
    # represents a canonical path in the ProjectTree. Should add validation that only
    # canonical paths are used with ProjectTree (probably in ProjectTree).
    return cls(tuple(PathGlob.create_from_spec(Dir(relative_to), relative_to, filespec)
                     for filespec in filespecs))


def scan_directory(project_tree, directory):
  """List Stats directly below the given path, relative to the ProjectTree.

  Fails eagerly if the path does not exist or is not a directory: since the input is
  a `Dir` instance, the path it represents should already have been confirmed to be an
  existing directory.

  :returns: A Stats object containing the members of the directory.
  """
  return Stats(tuple(project_tree.scandir(directory.path)))


def merge_paths(paths_list):
  """Merge Paths lists."""
  return Paths(tuple(p for paths in paths_list for p in paths.dependencies))


def apply_path_wildcard(stats, path_wildcard):
  """Filter the given Stats object using the given PathWildcard."""
  return Paths(tuple(Path(normpath(join(path_wildcard.symbolic_path, basename(s.path))), s)
                     for s in stats.dependencies
                     if fnmatch.fnmatch(basename(s.path), path_wildcard.wildcard)))


def apply_path_literal(dirs, path_literal):
  """Given a PathLiteral, generate a PathGlobs object with a longer canonical_at prefix.

  Expects to match zero or one directory.
  """
  if len(dirs.dependencies) > 1:
    raise AssertionError('{} matched more than one directory!: {}'.format(path_literal, dirs))

  # For each match, create a PathGlob.
  path_globs = tuple(PathGlob.create_from_spec(d.stat, d.path, path_literal.remainder)
                     for d in dirs.dependencies)
  return PathGlobs(path_globs)


def apply_path_dir_wildcard(dirs, path_dir_wildcard):
  """Given a PathDirWildcard, compute a PathGlobs object that encompasses its children.

  The resulting PathGlobs will have longer canonical prefixes than this wildcard, in the
  sense that they will be relative to known-canonical subdirectories.
  """
  # For each matching Path, create a PathGlob per remainder.
  path_globs = tuple(PathGlob.create_from_spec(d.stat, d.path, remainder)
                     for d in dirs.dependencies
                     for remainder in path_dir_wildcard.remainders)
  return PathGlobs(path_globs)


def resolve_dir_links(direct_paths, linked_dirs):
  """Given a set of Paths, and a resolved Dirs object per Link in the paths, return merged Dirs."""
  # Alias the resolved Dir with the symbolic name of the Paths used to resolve it.
  # Zip links to their directories.
  if len(direct_paths.links) != len(linked_dirs):
    raise ValueError('Expected to receive a Dirs object per Link. Got: {} vs {}'.format(
      direct_paths.links, linked_dirs))
  linked_paths = tuple(Path(l.path, dirs.dependencies[0].stat)
                       for l, dirs in zip(direct_paths.links, linked_dirs)
                       if len(dirs.dependencies) > 0)
  # Entries that were already directories, and Links that (recursively) pointed to directories.
  return Dirs(direct_paths.dirs + linked_paths)


def resolve_file_links(direct_stats, linked_files):
  return Files(tuple(f for files in (direct_stats.files, linked_files.dependencies) for f in files))


def read_link(project_tree, link):
  return ReadLink(project_tree.readlink(link.path))


def filter_paths(stats, path_literal):
  """Filter the given Stats object into Paths matching the given PathLiteral."""
  paths = tuple(Path(join(path_literal.symbolic_path, path_literal.literal), s)
                for s in stats.dependencies
                if basename(s.path) == path_literal.literal)
  return FilteredPaths(Paths(paths))


def filter_wildcard_paths(stats, path_dir_wildcard):
  """Filter the given Stats object into Paths matching the given PathLiteral.
  
  TODO: This can definitely be merged with filter_paths/PathLiteral now!
  """
  entries = [(s, basename(s.path)) for s in stats.dependencies]
  paths = tuple(Path(join(path_dir_wildcard.symbolic_path, basename), stat)
                for stat, basename in entries
                if fnmatch.fnmatch(basename, path_dir_wildcard.wildcard))
  return FilteredPaths(Paths(paths))


def file_content(project_tree, f):
  """Return a FileContent for a known-existing File.

  NB: This method fails eagerly, because it expects to be executed only after a caller has
  stat'd a path to determine that it is, in fact, an existing File.
  """
  return FileContent(f.path, project_tree.content(f.path))


def file_digest(project_tree, f):
  """Return a FileDigest for a known-existing File.

  See NB on file_content.
  """
  return FileDigest(f.path, sha1(project_tree.content(f.path)).digest())


def resolve_link(stats):
  """"""
  return stats


# TODO: The types here are currently lies. These are each wrappers around _Path_ objects
# for the relevant type of Stat.
Dirs = Collection.of(Dir)
Files = Collection.of(File)
Links = Collection.of(Link)


FilesContent = Collection.of(FileContent)
FilesDigest = Collection.of(FileDigest)


def create_fs_tasks():
  """Creates tasks that consume the native filesystem Node type."""
  return [
    # Glob execution.
    (Paths,
     [SelectDependencies(Paths, PathGlobs)],
     merge_paths),
    (Paths,
     [SelectProjection(Stats, Dir, ('canonical_stat',), PathWildcard),
      Select(PathWildcard)],
     apply_path_wildcard),
    (PathGlobs,
     [SelectProjection(Dirs, Paths, ('paths',), FilteredPaths),
      Select(PathLiteral)],
     apply_path_literal),
    (PathGlobs,
     [SelectProjection(Dirs, Paths, ('paths',), FilteredPaths),
      Select(PathDirWildcard)],
     apply_path_dir_wildcard),
    (FilteredPaths,
     [SelectProjection(Stats, Dir, ('canonical_stat',), PathLiteral),
      Select(PathLiteral)],
     filter_paths),
    (FilteredPaths,
     [SelectProjection(Stats, Dir, ('canonical_stat',), PathDirWildcard),
      Select(PathDirWildcard)],
     filter_wildcard_paths),
  ] + [
    # Link resolution.
    (Dirs,
     [Select(Paths),
      SelectDependencies(Dirs, Paths, field='link_stats')],
     resolve_dir_links),
    (Files,
     [Select(Paths),
      SelectDependencies(Files, Paths, field='link_stats')],
     resolve_file_links),
    (Dirs,
     [SelectProjection(Dirs, PathGlobs, ('path_globs',), ReadLink)],
     resolve_link),
    (Files,
     [SelectProjection(Files, PathGlobs, ('path_globs',), ReadLink)],
     resolve_link),
  ] + [
    # File content.
    (FilesContent,
     [SelectDependencies(FileContent, Files)],
     FilesContent),
    (FilesDigest,
     [SelectDependencies(FileDigest, Files)],
     FilesDigest),
  ]
