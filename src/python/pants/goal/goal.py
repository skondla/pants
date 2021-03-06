# coding=utf-8
# Copyright 2014 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import absolute_import, division, print_function, unicode_literals

from builtins import object

from future.utils import PY2

from pants.goal.error import GoalError
from pants.option.optionable import Optionable
from pants.util.memo import memoized


@memoized
def _create_stable_task_type(superclass, options_scope):
  """Creates a singleton (via `memoized`) subclass instance for the given superclass and scope.

  Currently we need to support registering the same task type multiple times in different
  scopes. However we still want to have each task class know the options scope it was
  registered in. So we create a synthetic subclass here.

  TODO(benjy): Revisit this when we revisit the task lifecycle. We probably want to have
  a task *instance* know its scope, but this means converting option registration from
  a class method to an instance method, and instantiating the task much sooner in the
  lifecycle.
  """
  subclass_name = '{0}_{1}'.format(superclass.__name__,
                                  options_scope.replace('.', '_').replace('-', '_'))
  if PY2:
    subclass_name = subclass_name.encode('utf-8')
  return type(subclass_name, (superclass,), {
    '__doc__': superclass.__doc__,
    '__module__': superclass.__module__,
    'options_scope': options_scope,
    '_stable_name': superclass.stable_name()
  })


class Goal(object):
  """Factory for objects representing goals.

  Ensures that we have exactly one instance per goal name.

  :API: public
  """
  _goal_by_name = dict()

  def __new__(cls, *args, **kwargs):
    raise TypeError('Do not instantiate {0}. Call by_name() instead.'.format(cls))

  @classmethod
  def register(cls, name, description, options_registrar_cls=None):
    """Register a goal description.

    Otherwise the description must be set when registering some task on the goal,
    which is clunky, and dependent on things like registration order of tasks in the goal.

    A goal that isn't explicitly registered with a description will fall back to the description
    of the task in that goal with the same name (if any).  So singleton goals (e.g., 'clean-all')
    need not be registered explicitly.  This method is primarily useful for setting a
    description on a generic goal like 'compile' or 'test', that multiple backends will
    register tasks on.

    :API: public

    :param string name: The name of the goal; ie: the way to specify it on the command line.
    :param string description: A description of the tasks in the goal do.
    :param :class:pants.option.Optionable options_registrar_cls: A class for registering options
           at the goal scope. Useful for registering recursive options on all tasks in a goal.
    :return: The freshly registered goal.
    :rtype: :class:`_Goal`
    """
    goal = cls.by_name(name)
    goal._description = description
    goal._options_registrar_cls = (options_registrar_cls.registrar_for_scope(name)
                                   if options_registrar_cls else None)
    return goal

  @classmethod
  def by_name(cls, name):
    """Returns the unique object representing the goal of the specified name.

    :API: public
    """
    if name not in cls._goal_by_name:
      cls._goal_by_name[name] = _Goal(name)
    return cls._goal_by_name[name]

  @classmethod
  def clear(cls):
    """Remove all goals and tasks.

    This method is EXCLUSIVELY for use in tests and during pantsd startup.

    :API: public
    """
    cls._goal_by_name.clear()

  @staticmethod
  def scope(goal_name, task_name):
    """Returns options scope for specified task in specified goal.

    :API: public
    """
    return goal_name if goal_name == task_name else '{0}.{1}'.format(goal_name, task_name)

  @staticmethod
  def all():
    """Returns all active registered goals, sorted alphabetically by name.

    :API: public
    """
    return [goal for _, goal in sorted(Goal._goal_by_name.items()) if goal.active]

  @classmethod
  def get_optionables(cls):
    for goal in cls.all():
      if goal._options_registrar_cls:
        yield goal._options_registrar_cls
      for task_type in goal.task_types():
        yield task_type

  @classmethod
  def subsystems(cls):
    """Returns all subsystem types used by all tasks, in no particular order.

    :API: public
    """
    ret = set()
    for goal in cls.all():
      ret.update(goal.subsystems())
    return ret


class _Goal(object):
  def __init__(self, name):
    """Don't call this directly.

    Create goals only through the Goal.by_name() factory.
    """
    Optionable.validate_scope_name_component(name)
    self.name = name
    self._description = ''
    self._options_registrar_cls = None
    self.serialize = False
    self._task_type_by_name = {}  # name -> Task subclass.
    self._ordered_task_names = []  # The task names, in the order imposed by registration.

  @property
  def description(self):
    if self._description:
      return self._description
    # Return the docstring for the Task registered under the same name as this goal, if any.
    # This is a very common case, and therefore a useful idiom.
    namesake_task = self._task_type_by_name.get(self.name)
    if namesake_task and namesake_task.__doc__:
      # First line of docstring.
      return namesake_task.__doc__
    return ''

  @property
  def description_first_line(self):
    # TODO: This is repetitive of Optionable.get_description(), which is used by v2 Goals.
    return self.description.partition('\n')[0].strip()

  def register_options(self, options):
    if self._options_registrar_cls:
      self._options_registrar_cls.register_options_on_scope(options)

  def install(self, task_registrar, first=False, replace=False, before=None, after=None):
    """Installs the given task in this goal.

    The placement of the task in this goal's execution list defaults to the end but its position
    can be influenced by specifying exactly one of the following arguments:

    first: Places the task 1st in the execution list.
    replace: Removes all existing tasks in this goal and installs this task.
    before: Places the task before the named task in the execution list.
    after: Places the task after the named task in the execution list.

    :API: public
    """
    if [bool(place) for place in [first, replace, before, after]].count(True) > 1:
      raise GoalError('Can only specify one of first, replace, before or after')

    otn = self._ordered_task_names
    if replace:
      for tt in self.task_types():
        tt.options_scope = None
      del otn[:]
      self._task_type_by_name = {}

    task_name = task_registrar.name
    if task_name in self._task_type_by_name:
      raise GoalError(
        'Can only specify a task name once per goal, saw multiple values for {} in goal {}'.format(
          task_name,
          self.name))
    Optionable.validate_scope_name_component(task_name)
    options_scope = Goal.scope(self.name, task_name)

    task_type = _create_stable_task_type(task_registrar.task_type, options_scope)

    if first:
      otn.insert(0, task_name)
    elif before in otn:
      otn.insert(otn.index(before), task_name)
    elif after in otn:
      otn.insert(otn.index(after) + 1, task_name)
    else:
      otn.append(task_name)

    self._task_type_by_name[task_name] = task_type

    if task_registrar.serialize:
      self.serialize = True

    return self

  def uninstall_task(self, name):
    """Removes the named task from this goal.

    Allows external plugins to modify the execution plan. Use with caution.

    Note: Does not relax a serialization requirement that originated
    from the uninstalled task's install() call.

    :API: public
    """
    if name in self._task_type_by_name:
      self._task_type_by_name[name].options_scope = None
      del self._task_type_by_name[name]
      self._ordered_task_names = [x for x in self._ordered_task_names if x != name]
    else:
      raise GoalError('Cannot uninstall unknown task: {0}'.format(name))

  def subsystems(self):
    """Returns all subsystem types used by tasks in this goal, in no particular order."""
    ret = set()
    for task_type in self.task_types():
      ret.update([dep.subsystem_cls for dep in task_type.subsystem_dependencies_iter()])
    return ret

  def ordered_task_names(self):
    """The task names in this goal, in registration order."""
    return self._ordered_task_names

  def task_type_by_name(self, name):
    """The task type registered under the given name."""
    return self._task_type_by_name[name]

  def task_types(self):
    """Returns the task types in this goal, unordered."""
    return list(self._task_type_by_name.values())

  def task_items(self):
    for name, task_type in self._task_type_by_name.items():
      yield name, task_type

  def has_task_of_type(self, typ):
    """Returns True if this goal has a task of the given type (or a subtype of it)."""
    for task_type in self.task_types():
      if issubclass(task_type, typ):
        return True
    return False

  @property
  def active(self):
    """Return `True` if this goal has tasks installed.

    Some goals are installed in pants core without associated tasks in anticipation of plugins
    providing tasks that implement the goal being installed. If no such plugins are installed, the
    goal may be inactive in the repo.
    """
    return len(self._task_type_by_name) > 0

  def __repr__(self):
    return self.name
