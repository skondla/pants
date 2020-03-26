# Copyright 2014 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import unittest
from textwrap import dedent

from pants.base.payload import Payload
from pants.build_graph.address_lookup_error import AddressLookupError
from pants.build_graph.build_file_aliases import BuildFileAliases
from pants.build_graph.files import Files
from pants.build_graph.target import Target
from pants.engine.fs import EMPTY_SNAPSHOT
from pants.source.wrapped_globs import EagerFilesetWithSpec, Filespec, LazyFilesetWithSpec
from pants.testutil.test_base import TestBase


class DummyTarget(Target):
    def __init__(self, address=None, payload=None, sources=None, **kwargs):
        payload = payload or Payload()
        payload.add_fields(
            {"sources": self.create_sources_field(sources, address.spec_path, key_arg="sources")}
        )
        super().__init__(address=address, payload=payload, **kwargs)


class FilesetRelPathWrapperTest(TestBase):
    @classmethod
    def alias_groups(cls):
        return BuildFileAliases(targets={"dummy_target": DummyTarget})

    def setUp(self) -> None:
        super().setUp()
        self.create_file("y/morx.java")
        self.create_file("y/fleem.java")
        self.create_file("z/w/foo.java")
        self.create_link("y", "z/w/y")

    def test_no_dir_glob(self) -> None:
        self.add_to_build_file("y/BUILD", 'dummy_target(name="y", sources=["*"])')
        self.context().scan()

    def test_no_dir_glob_question(self) -> None:
        self.add_to_build_file("y/BUILD", 'dummy_target(name="y", sources=["?"])')
        self.context().scan()

    def _spec_test(self, spec: str, expected: Filespec) -> None:
        self.add_to_build_file("y/BUILD", f'dummy_target(name="y", sources={spec})')
        graph = self.context().scan()
        globs = graph.get_target_from_spec("y").globs_relative_to_buildroot()
        self.assertEqual(expected, globs)

    def test_glob_to_spec(self) -> None:
        self._spec_test('["*.java"]', {"globs": ["y/*.java"]})

    def test_glob_to_spec_exclude(self) -> None:
        self._spec_test(
            '["*.java", "!fleem.java"]',
            {"globs": ["y/*.java"], "exclude": [{"globs": ["y/fleem.java"]}]},
        )

    def test_glob_mid_single(self) -> None:
        self._spec_test('["a/*/Fleem.java"]', {"globs": ["y/a/*/Fleem.java"]})

    def test_glob_to_spec_list(self) -> None:
        self._spec_test('["fleem.java", "morx.java"]', {"globs": ["y/fleem.java", "y/morx.java"]})

    def test_glob_exclude(self) -> None:
        self.add_to_build_file(
            "y/BUILD",
            dedent(
                """
                dummy_target(name="y", sources=["*.java", "!fleem.java"])
                """
            ),
        )
        graph = self.context().scan()
        assert ["morx.java"] == list(
            graph.get_target_from_spec("y").sources_relative_to_source_root()
        )

    def test_glob_with_folder_with_only_folders(self) -> None:
        self.add_to_build_file(
            "z/BUILD",
            dedent(
                """
                dummy_target(name="z", sources=["*", "!BUILD"])
                """
            ),
        )
        graph = self.context().scan()
        self.assertEqual(
            [], list(graph.get_target_from_spec("z").sources_relative_to_source_root())
        )

    def test_glob_exclude_doesnt_modify_exclude_array(self) -> None:
        self.add_to_build_file(
            "y/BUILD",
            dedent(
                """
                list_of_files = ["fleem.java"]
                dummy_target(name="y", sources=["*.java", *(f"!{fp}" for fp in list_of_files)])
                dummy_target(name="z", sources=list_of_files)
                """
            ),
        )

        graph = self.context().scan()

        self.assertEqual(
            ["fleem.java"],
            list(graph.get_target_from_spec("y:z").sources_relative_to_source_root()),
        )

    def test_subdir_glob(self) -> None:
        self.add_to_build_file("y/BUILD", 'dummy_target(name="y", sources=["dir/*.scala"])')
        self.context().scan()

    def test_subdir_glob_question(self) -> None:
        self.add_to_build_file("y/BUILD", 'dummy_target(name="y", sources=["dir/?.scala"])')
        self.context().scan()

    def test_subdir_bracket_glob(self) -> None:
        self.add_to_build_file(
            "y/BUILD",
            dedent(
                """
                dummy_target(name="y", sources=["dir/[dir1, dir2]/*.scala"])
                """
            ),
        )
        self.context().scan()

    def test_subdir_with_dir_glob(self) -> None:
        self.add_to_build_file("y/BUILD", 'dummy_target(name="y", sources=["dir/**/*.scala"])')
        self.context().scan()

    @unittest.skip(reason="TODO: #4760")
    def test_parent_dir_glob(self) -> None:
        self.add_to_build_file("y/BUILD", 'dummy_target(name="y", sources=["../*.scala"])')
        with self.assertRaises(AddressLookupError):
            self.context().scan()

    @unittest.skip(reason="TODO: #4760")
    def test_parent_dir_glob_question(self) -> None:
        self.add_to_build_file("y/BUILD", 'dummy_target(name="y", sources=["../?.scala"])')
        with self.assertRaises(AddressLookupError):
            self.context().scan()

    @unittest.skip(reason="TODO: #4760")
    def test_parent_dir_bracket_glob_question(self) -> None:
        self.add_to_build_file(
            "y/BUILD",
            dedent(
                """
                dummy_target(name="y", sources=["../[dir1, dir2]/?.scala"])
                """
            ),
        )
        with self.assertRaises(AddressLookupError):
            self.context().scan()

    @unittest.skip(reason="TODO: #4760")
    def test_parent_dir_bracket(self) -> None:
        self.add_to_build_file(
            "y/BUILD",
            dedent(
                """
                dummy_target(name="y", sources=["../[dir1, dir2]/File.scala"])
                """
            ),
        )
        with self.assertRaises(AddressLookupError):
            self.context().scan()

    def test_absolute_dir_glob(self) -> None:
        self.add_to_build_file("y/BUILD", 'dummy_target(name="y", sources=["/root/*.scala"])')
        with self.assertRaises(AddressLookupError):
            self.context().scan()

    def test_absolute_dir_glob_question(self) -> None:
        self.add_to_build_file("y/BUILD", 'dummy_target(name="y", sources=["/root/?.scala"])')
        with self.assertRaises(AddressLookupError):
            self.context().scan()


class FilesetWithSpecTest(TestBase):
    @classmethod
    def alias_groups(cls):
        return BuildFileAliases(targets={"files": Files})

    def test_lazy_fileset_with_spec_fails_if_filespec_not_prefixed_by_relroot(self) -> None:
        with self.assertRaises(ValueError):
            LazyFilesetWithSpec("foo", {"globs": ["notfoo/a.txt"]}, lambda: ["foo/a.txt"])

    def test_eager_fileset_with_spec_fails_if_filespec_not_prefixed_by_relroot(self) -> None:
        with self.assertRaises(ValueError):
            EagerFilesetWithSpec("foo", {"globs": ["notfoo/a.txt"]}, EMPTY_SNAPSHOT)

    def test_lazy_fileset_with_spec_fails_if_exclude_filespec_not_prefixed_by_relroot(self) -> None:
        with self.assertRaises(ValueError):
            LazyFilesetWithSpec(
                "foo",
                {"globs": [], "exclude": [{"globs": ["notfoo/a.txt"]}]},
                lambda: ["foo/a.txt"],
            )

    def test_eager_fileset_with_spec_fails_if_exclude_filespec_not_prefixed_by_relroot(
        self,
    ) -> None:
        with self.assertRaises(ValueError):
            EagerFilesetWithSpec(
                "foo", {"globs": [], "exclude": [{"globs": ["notfoo/a.txt"]}]}, EMPTY_SNAPSHOT
            )

    def test_iter_relative_paths(self) -> None:
        self.create_files("test_root", ["a", "b", "c"])
        efws = self.sources_for(["a", "b", "c"], "test_root")
        self.assertEqual(
            efws.files_hash, b"cb11a7f0b5a1e22b93c36783608ba531ea831c2f68a5c9f9498417b211bcfea4",
        )
        self.assertEqual(
            list(efws.paths_from_buildroot_iter()), ["test_root/a", "test_root/b", "test_root/c"],
        )

    def test_source_snapshot(self) -> None:
        self.create_file("package/dir/foo")
        self.add_to_build_file("package/dir", 'files(name = "target", sources = ["foo"])')
        target = self.target("package/dir:target")
        snapshot = target.sources_snapshot(scheduler=self.scheduler)
        self.assertEqual(("package/dir/foo",), snapshot.files)
        self.assertEqual(target.sources_relative_to_target_base().files, ("foo",))
        self.assertEqual(target.sources_relative_to_buildroot(), ["package/dir/foo"])
