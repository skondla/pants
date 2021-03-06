# Copyright 2014 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_tests(
  name = 'build_environment',
  sources = ['test_build_environment.py'],
  dependencies = [
    'src/python/pants/base:build_environment',
    'src/python/pants/util:contextutil',
    'src/python/pants/util:fileutil',
  ]
)

python_tests(
  name = 'build_root',
  sources = ['test_build_root.py'],
  dependencies = [
    'src/python/pants/base:build_root',
    'src/python/pants/util:contextutil',
    'src/python/pants/util:dirutil',
    'tests/python/pants_test:test_base',
  ]
)

python_tests(
  name = 'exclude_target_regexp_integration',
  sources = [ 'test_exclude_target_regexp_integration.py' ],
  dependencies = [
    '3rdparty/python:future',
    'src/python/pants/util:process_handler',
    'tests/python/pants_test:int-test',
  ],
  tags = {'integration'},
  timeout = 120,
)

python_tests(
  name = 'cmd_line_spec_parser',
  sources = ['test_cmd_line_spec_parser.py'],
  dependencies = [
    '3rdparty/python/twitter/commons:twitter.common.collections',
    'src/python/pants/base:cmd_line_spec_parser',
    'src/python/pants/build_graph',
    'tests/python/pants_test:test_base',
  ]
)

python_library(
  name = 'context_utils',
  sources = ['context_utils.py'],
  dependencies = [
    '3rdparty/python:future',
    '3rdparty/python/twitter/commons:twitter.common.collections',
    'src/python/pants/base:workunit',
    'src/python/pants/build_graph',
    'src/python/pants/goal:context',
    'src/python/pants/goal:run_tracker',
    'tests/python/pants_test/option/util',
  ]
)

python_tests(
  name = 'deprecated',
  sources = ['test_deprecated.py'],
  dependencies = [
    '3rdparty/python:mock',
    '3rdparty/python:future',
    'src/python/pants/base:deprecated',
    'src/python/pants/util:collections',
    'src/python/pants:version',
    'tests/python/pants_test:test_base',
  ]
)

python_tests(
  name = 'filesystem_build_file',
  sources = ['test_filesystem_build_file.py'],
  dependencies = [
    '3rdparty/python:pathspec',
    '3rdparty/python:six',
    '3rdparty/python/twitter/commons:twitter.common.collections',
    'src/python/pants/base:build_file',
    'src/python/pants/util:dirutil',
  ]
)

python_tests(
  name = 'fingerprint_strategy',
  sources = ['test_fingerprint_strategy.py'],
  dependencies = [
    'src/python/pants/base:fingerprint_strategy',
    'tests/python/pants_test:test_base',
  ]
)

python_tests(
  name = 'generator',
  sources = ['test_generator.py'],
  dependencies = [
    'src/python/pants/base:generator',
    'tests/python/pants_test:test_base',
  ]
)

python_tests(
  name = 'hash_utils',
  sources = ['test_hash_utils.py'],
  dependencies = [
    '3rdparty/python:future',
    '3rdparty/python/twitter/commons:twitter.common.collections',
    'src/python/pants/base:hash_utils',
    'src/python/pants/util:contextutil',
  ]
)

python_tests(
  name = 'pants_ignore_file_system',
  sources = ['test_pants_ignore_file_system.py'],
  dependencies = [
    ':pants_ignore_test_base',
    'src/python/pants/base:project_tree',
  ]
)

python_library(
  name = 'pants_ignore_test_base',
  sources = ['pants_ignore_test_base.py'],
  dependencies = [
    ':project_tree_test_base',
  ]
)

python_tests(
  name = 'payload',
  sources = ['test_payload.py'],
  dependencies = [
    'src/python/pants/base:payload',
    'src/python/pants/base:payload_field',
    'src/python/pants/build_graph',
    'tests/python/pants_test:test_base',
  ]
)

python_tests(
  name = 'payload_field',
  sources = ['test_payload_field.py'],
  dependencies = [
    'src/python/pants/java/jar',
    'src/python/pants/backend/python:python_requirement',
    'src/python/pants/base:payload_field',
    'tests/python/pants_test:test_base',
  ]
)

python_library(
  name = 'project_tree_test_base',
  sources = ['project_tree_test_base.py'],
  dependencies = [
    'src/python/pants/util:dirutil',
    'src/python/pants/util:meta',
  ]
)

python_tests(
  name = 'revision',
  sources = ['test_revision.py'],
  dependencies = [
    'src/python/pants/base:revision',
    'tests/python/pants_test:test_base',
  ]
)

python_tests(
  name = 'run_info',
  sources = ['test_run_info.py'],
  dependencies = [
    '3rdparty/python:future',
    'src/python/pants/base:run_info',
    'src/python/pants/util:contextutil',
    'tests/python/pants_test:test_base',
  ]
)

python_tests(
  name = 'worker_pool',
  sources = ['test_worker_pool.py'],
  dependencies = [
    '3rdparty/python:future',
    'src/python/pants/base:worker_pool',
    'src/python/pants/util:contextutil',
  ]
)

python_tests(
  name = 'validation',
  sources = ['test_validation.py'],
  dependencies = [
    'src/python/pants/base:validation',
  ]
)

python_tests(
  name = 'exception_sink',
  sources = ['test_exception_sink.py'],
  dependencies = [
    '3rdparty/python:future',
    '3rdparty/python:mock',
    'src/python/pants/base:exception_sink',
    'src/python/pants/util:contextutil',
    'src/python/pants/util:dirutil',
    'src/python/pants/util:osutil',
    'tests/python/pants_test:test_base',
    'tests/python/pants_test/option/util',
    'tests/python/pants_test/testutils:py2_compat',
  ],
  tags={'platform_specific_behavior'},
)

python_tests(
  name = 'exception_sink_integration',
  sources = ['test_exception_sink_integration.py'],
  dependencies = [
    '3rdparty/python:future',
    '3rdparty/python:mock',
    'src/python/pants/base:exception_sink',
    'src/python/pants/util:osutil',
    'tests/python/pants_test:int-test',
    'tests/python/pants_test/testutils:py2_compat',
  ],
  tags = {'platform_specific_behavior', 'integration'},
  timeout = 360,
)

python_tests(
  name = 'exiter_integration',
  sources = [ 'test_exiter_integration.py' ],
  dependencies = [
    'tests/python/pants_test:int-test',
  ],
  tags = {'integration'},
  timeout = 120,
)
