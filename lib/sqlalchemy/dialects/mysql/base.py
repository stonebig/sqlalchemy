# mysql/base.py
# Copyright (C) 2005-2019 the SQLAlchemy authors and contributors
# <see AUTHORS file>
#
# This module is part of SQLAlchemy and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

r"""

.. dialect:: mysql
    :name: MySQL

Supported Versions and Features
-------------------------------

SQLAlchemy supports MySQL starting with version 4.1 through modern releases.
However, no heroic measures are taken to work around major missing
SQL features - if your server version does not support sub-selects, for
example, they won't work in SQLAlchemy either.

See the official MySQL documentation for detailed information about features
supported in any given server release.

.. _mysql_connection_timeouts:

Connection Timeouts and Disconnects
-----------------------------------

MySQL features an automatic connection close behavior, for connections that
have been idle for a fixed period of time, defaulting to eight hours.
To circumvent having this issue, use
the :paramref:`.create_engine.pool_recycle` option which ensures that
a connection will be discarded and replaced with a new one if it has been
present in the pool for a fixed number of seconds::

    engine = create_engine('mysql+mysqldb://...', pool_recycle=3600)

For more comprehensive disconnect detection of pooled connections, including
accommodation of  server restarts and network issues, a pre-ping approach may
be employed.  See :ref:`pool_disconnects` for current approaches.

.. seealso::

    :ref:`pool_disconnects` - Background on several techniques for dealing
    with timed out connections as well as database restarts.

.. _mysql_storage_engines:

CREATE TABLE arguments including Storage Engines
------------------------------------------------

MySQL's CREATE TABLE syntax includes a wide array of special options,
including ``ENGINE``, ``CHARSET``, ``MAX_ROWS``, ``ROW_FORMAT``,
``INSERT_METHOD``, and many more.
To accommodate the rendering of these arguments, specify the form
``mysql_argument_name="value"``.  For example, to specify a table with
``ENGINE`` of ``InnoDB``, ``CHARSET`` of ``utf8mb4``, and ``KEY_BLOCK_SIZE``
of ``1024``::

  Table('mytable', metadata,
        Column('data', String(32)),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
        mysql_key_block_size="1024"
       )

The MySQL dialect will normally transfer any keyword specified as
``mysql_keyword_name`` to be rendered as ``KEYWORD_NAME`` in the
``CREATE TABLE`` statement.  A handful of these names will render with a space
instead of an underscore; to support this, the MySQL dialect has awareness of
these particular names, which include ``DATA DIRECTORY``
(e.g. ``mysql_data_directory``), ``CHARACTER SET`` (e.g.
``mysql_character_set``) and ``INDEX DIRECTORY`` (e.g.
``mysql_index_directory``).

The most common argument is ``mysql_engine``, which refers to the storage
engine for the table.  Historically, MySQL server installations would default
to ``MyISAM`` for this value, although newer versions may be defaulting
to ``InnoDB``.  The ``InnoDB`` engine is typically preferred for its support
of transactions and foreign keys.

A :class:`.Table` that is created in a MySQL database with a storage engine
of ``MyISAM`` will be essentially non-transactional, meaning any
INSERT/UPDATE/DELETE statement referring to this table will be invoked as
autocommit.   It also will have no support for foreign key constraints; while
the ``CREATE TABLE`` statement accepts foreign key options, when using the
``MyISAM`` storage engine these arguments are discarded.  Reflecting such a
table will also produce no foreign key constraint information.

For fully atomic transactions as well as support for foreign key
constraints, all participating ``CREATE TABLE`` statements must specify a
transactional engine, which in the vast majority of cases is ``InnoDB``.

.. seealso::

    `The InnoDB Storage Engine
    <http://dev.mysql.com/doc/refman/5.0/en/innodb-storage-engine.html>`_ -
    on the MySQL website.

Case Sensitivity and Table Reflection
-------------------------------------

MySQL has inconsistent support for case-sensitive identifier
names, basing support on specific details of the underlying
operating system. However, it has been observed that no matter
what case sensitivity behavior is present, the names of tables in
foreign key declarations are *always* received from the database
as all-lower case, making it impossible to accurately reflect a
schema where inter-related tables use mixed-case identifier names.

Therefore it is strongly advised that table names be declared as
all lower case both within SQLAlchemy as well as on the MySQL
database itself, especially if database reflection features are
to be used.

.. _mysql_isolation_level:

Transaction Isolation Level
---------------------------

All MySQL dialects support setting of transaction isolation level both via a
dialect-specific parameter :paramref:`.create_engine.isolation_level` accepted
by :func:`.create_engine`, as well as the
:paramref:`.Connection.execution_options.isolation_level` argument as passed to
:meth:`.Connection.execution_options`. This feature works by issuing the
command ``SET SESSION TRANSACTION ISOLATION LEVEL <level>`` for each new
connection.  For the special AUTOCOMMIT isolation level, DBAPI-specific
techniques are used.

To set isolation level using :func:`.create_engine`::

    engine = create_engine(
                    "mysql://scott:tiger@localhost/test",
                    isolation_level="READ UNCOMMITTED"
                )

To set using per-connection execution options::

    connection = engine.connect()
    connection = connection.execution_options(
        isolation_level="READ COMMITTED"
    )

Valid values for ``isolation_level`` include:

* ``READ COMMITTED``
* ``READ UNCOMMITTED``
* ``REPEATABLE READ``
* ``SERIALIZABLE``
* ``AUTOCOMMIT``

The special ``AUTOCOMMIT`` value makes use of the various "autocommit"
attributes provided by specific DBAPIs, and is currently supported by
MySQLdb, MySQL-Client, MySQL-Connector Python, and PyMySQL.   Using it,
the MySQL connection will return true for the value of
``SELECT @@autocommit;``.

.. versionadded:: 1.1 - added support for the AUTOCOMMIT isolation level.

AUTO_INCREMENT Behavior
-----------------------

When creating tables, SQLAlchemy will automatically set ``AUTO_INCREMENT`` on
the first :class:`.Integer` primary key column which is not marked as a
foreign key::

  >>> t = Table('mytable', metadata,
  ...   Column('mytable_id', Integer, primary_key=True)
  ... )
  >>> t.create()
  CREATE TABLE mytable (
          id INTEGER NOT NULL AUTO_INCREMENT,
          PRIMARY KEY (id)
  )

You can disable this behavior by passing ``False`` to the
:paramref:`~.Column.autoincrement` argument of :class:`.Column`.  This flag
can also be used to enable auto-increment on a secondary column in a
multi-column key for some storage engines::

  Table('mytable', metadata,
        Column('gid', Integer, primary_key=True, autoincrement=False),
        Column('id', Integer, primary_key=True)
       )

.. _mysql_ss_cursors:

Server Side Cursors
-------------------

Server-side cursor support is available for the MySQLdb and PyMySQL dialects.
From a MySQL point of view this means that the ``MySQLdb.cursors.SSCursor`` or
``pymysql.cursors.SSCursor`` class is used when building up the cursor which
will receive results.  The most typical way of invoking this feature is via the
:paramref:`.Connection.execution_options.stream_results` connection execution
option.   Server side cursors can also be enabled for all SELECT statements
unconditionally by passing ``server_side_cursors=True`` to
:func:`.create_engine`.

.. versionadded:: 1.1.4 - added server-side cursor support.

.. _mysql_unicode:

Unicode
-------

Charset Selection
~~~~~~~~~~~~~~~~~

Most MySQL DBAPIs offer the option to set the client character set for
a connection.   This is typically delivered using the ``charset`` parameter
in the URL, such as::

    e = create_engine(
        "mysql+pymysql://scott:tiger@localhost/test?charset=utf8mb4")

This charset is the **client character set** for the connection.  Some
MySQL DBAPIs will default this to a value such as ``latin1``, and some
will make use of the ``default-character-set`` setting in the ``my.cnf``
file as well.   Documentation for the DBAPI in use should be consulted
for specific behavior.

The encoding used for Unicode has traditionally been ``'utf8'``.  However,
for MySQL versions 5.5.3 on forward, a new MySQL-specific encoding
``'utf8mb4'`` has been introduced, and as of MySQL 8.0 a warning is emitted
by the server if plain ``utf8`` is specified within any server-side
directives, replaced with ``utf8mb3``.   The rationale for this new encoding
is due to the fact that MySQL's legacy utf-8 encoding only supports
codepoints up to three bytes instead of four.  Therefore,
when communicating with a MySQL database
that includes codepoints more than three bytes in size,
this new charset is preferred, if supported by both the database as well
as the client DBAPI, as in::

    e = create_engine(
        "mysql+pymysql://scott:tiger@localhost/test?charset=utf8mb4")

All modern DBAPIs should support the ``utf8mb4`` charset.

In order to use ``utf8mb4`` encoding for a schema that was created with  legacy
``utf8``, changes to the MySQL schema and/or server configuration may be
required.

.. seealso::

    `The utf8mb4 Character Set \
    <http://dev.mysql.com/doc/refman/5.5/en/charset-unicode-utf8mb4.html>`_ - \
    in the MySQL documentation

.. _mysql_binary_introducer:

Dealing with Binary Data Warnings and Unicode
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

MySQL versions 5.6, 5.7 and later (not MariaDB at the time of this writing) now
emit a warning when attempting to pass binary data to the database, while a
character set encoding is also in place, when the binary data itself is not
valid for that encoding::

    default.py:509: Warning: (1300, "Invalid utf8mb4 character string:
    'F9876A'")
      cursor.execute(statement, parameters)

This warning is due to the fact that the MySQL client library is attempting to
interpret the binary string as a unicode object even if a datatype such
as :class:`.LargeBinary` is in use.   To resolve this, the SQL statement requires
a binary "character set introducer" be present before any non-NULL value
that renders like this::

    INSERT INTO table (data) VALUES (_binary %s)

These character set introducers are provided by the DBAPI driver, assuming the
use of mysqlclient or PyMySQL (both of which are recommended).  Add the query
string parameter ``binary_prefix=true`` to the URL to repair this warning::

    # mysqlclient
    engine = create_engine(
        "mysql+mysqldb://scott:tiger@localhost/test?charset=utf8mb4&binary_prefix=true")

    # PyMySQL
    engine = create_engine(
        "mysql+pymysql://scott:tiger@localhost/test?charset=utf8mb4&binary_prefix=true")


The ``binary_prefix`` flag may or may not be supported by other MySQL drivers.

SQLAlchemy itself cannot render this ``_binary`` prefix reliably, as it does
not work with the NULL value, which is valid to be sent as a bound parameter.
As the MySQL driver renders parameters directly into the SQL string, it's the
most efficient place for this additional keyword to be passed.

.. seealso::

    `Character set introducers <https://dev.mysql.com/doc/refman/5.7/en/charset-introducer.html>`_ - on the MySQL website


ANSI Quoting Style
------------------

MySQL features two varieties of identifier "quoting style", one using
backticks and the other using quotes, e.g. ```some_identifier```  vs.
``"some_identifier"``.   All MySQL dialects detect which version
is in use by checking the value of ``sql_mode`` when a connection is first
established with a particular :class:`.Engine`.  This quoting style comes
into play when rendering table and column names as well as when reflecting
existing database structures.  The detection is entirely automatic and
no special configuration is needed to use either quoting style.

MySQL SQL Extensions
--------------------

Many of the MySQL SQL extensions are handled through SQLAlchemy's generic
function and operator support::

  table.select(table.c.password==func.md5('plaintext'))
  table.select(table.c.username.op('regexp')('^[a-d]'))

And of course any valid MySQL statement can be executed as a string as well.

Some limited direct support for MySQL extensions to SQL is currently
available.

* INSERT..ON DUPLICATE KEY UPDATE:  See
  :ref:`mysql_insert_on_duplicate_key_update`

* SELECT pragma, use :meth:`.Select.prefix_with` and :meth:`.Query.prefix_with`::

    select(...).prefix_with(['HIGH_PRIORITY', 'SQL_SMALL_RESULT'])

* UPDATE with LIMIT::

    update(..., mysql_limit=10)

* optimizer hints, use :meth:`.Select.prefix_with` and :meth:`.Query.prefix_with`::

    select(...).prefix_with("/*+ NO_RANGE_OPTIMIZATION(t4 PRIMARY) */")

* index hints, use :meth:`.Select.with_hint` and :meth:`.Query.with_hint`::

    select(...).with_hint(some_table, "USE INDEX xyz")

.. _mysql_insert_on_duplicate_key_update:

INSERT...ON DUPLICATE KEY UPDATE (Upsert)
------------------------------------------

MySQL allows "upserts" (update or insert)
of rows into a table via the ``ON DUPLICATE KEY UPDATE`` clause of the
``INSERT`` statement.  A candidate row will only be inserted if that row does
not match an existing primary or unique key in the table; otherwise, an UPDATE
will be performed.   The statement allows for separate specification of the
values to INSERT versus the values for UPDATE.

SQLAlchemy provides ``ON DUPLICATE KEY UPDATE`` support via the MySQL-specific
:func:`.mysql.dml.insert()` function, which provides
the generative method :meth:`~.mysql.dml.Insert.on_duplicate_key_update`::

    from sqlalchemy.dialects.mysql import insert

    insert_stmt = insert(my_table).values(
        id='some_existing_id',
        data='inserted value')

    on_duplicate_key_stmt = insert_stmt.on_duplicate_key_update(
        data=insert_stmt.inserted.data,
        status='U'
    )

    conn.execute(on_duplicate_key_stmt)

Unlike PostgreSQL's "ON CONFLICT" phrase, the "ON DUPLICATE KEY UPDATE"
phrase will always match on any primary key or unique key, and will always
perform an UPDATE if there's a match; there are no options for it to raise
an error or to skip performing an UPDATE.

``ON DUPLICATE KEY UPDATE`` is used to perform an update of the already
existing row, using any combination of new values as well as values
from the proposed insertion.   These values are normally specified using
keyword arguments passed to the
:meth:`~.mysql.dml.Insert.on_duplicate_key_update`
given column key values (usually the name of the column, unless it
specifies :paramref:`.Column.key`) as keys and literal or SQL expressions
as values::

    on_duplicate_key_stmt = insert_stmt.on_duplicate_key_update(
        data="some data",
        updated_at=func.current_timestamp(),
    )

In a manner similar to that of :meth:`.UpdateBase.values`, other parameter
forms are accepted, including a single dictionary::

    on_duplicate_key_stmt = insert_stmt.on_duplicate_key_update(
        {"data": "some data", "updated_at": func.current_timestamp()},
    )

as well as a list of 2-tuples, which will automatically provide
a parameter-ordered UPDATE statement in a manner similar to that described
at :ref:`updates_order_parameters`.  Unlike the :class:`.Update` object,
no special flag is needed to specify the intent since the argument form is
this context is unambiguous::

    on_duplicate_key_stmt = insert_stmt.on_duplicate_key_update(
        [
            ("data", "some data"),
            ("updated_at", func.current_timestamp()),
        ],
    )

.. versionchanged:: 1.3 support for parameter-ordered UPDATE clause within
   MySQL ON DUPLICATE KEY UPDATE

.. warning::

    The :meth:`.Insert.on_duplicate_key_update` method does **not** take into
    account Python-side default UPDATE values or generation functions, e.g.
    e.g. those specified using :paramref:`.Column.onupdate`.
    These values will not be exercised for an ON DUPLICATE KEY style of UPDATE,
    unless they are manually specified explicitly in the parameters.



In order to refer to the proposed insertion row, the special alias
:attr:`~.mysql.dml.Insert.inserted` is available as an attribute on
the :class:`.mysql.dml.Insert` object; this object is a
:class:`.ColumnCollection` which contains all columns of the target
table::

    from sqlalchemy.dialects.mysql import insert

    stmt = insert(my_table).values(
        id='some_id',
        data='inserted value',
        author='jlh')
    do_update_stmt = stmt.on_duplicate_key_update(
        data="updated value",
        author=stmt.inserted.author
    )
    conn.execute(do_update_stmt)

When rendered, the "inserted" namespace will produce the expression
``VALUES(<columnname>)``.

.. versionadded:: 1.2 Added support for MySQL ON DUPLICATE KEY UPDATE clause



rowcount Support
----------------

SQLAlchemy standardizes the DBAPI ``cursor.rowcount`` attribute to be the
usual definition of "number of rows matched by an UPDATE or DELETE" statement.
This is in contradiction to the default setting on most MySQL DBAPI drivers,
which is "number of rows actually modified/deleted".  For this reason, the
SQLAlchemy MySQL dialects always add the ``constants.CLIENT.FOUND_ROWS``
flag, or whatever is equivalent for the target dialect, upon connection.
This setting is currently hardcoded.

.. seealso::

    :attr:`.ResultProxy.rowcount`


CAST Support
------------

MySQL documents the CAST operator as available in version 4.0.2.  When using
the SQLAlchemy :func:`.cast` function, SQLAlchemy
will not render the CAST token on MySQL before this version, based on server
version detection, instead rendering the internal expression directly.

CAST may still not be desirable on an early MySQL version post-4.0.2, as it
didn't add all datatype support until 4.1.1.   If your application falls into
this narrow area, the behavior of CAST can be controlled using the
:ref:`sqlalchemy.ext.compiler_toplevel` system, as per the recipe below::

    from sqlalchemy.sql.expression import Cast
    from sqlalchemy.ext.compiler import compiles

    @compiles(Cast, 'mysql')
    def _check_mysql_version(element, compiler, **kw):
        if compiler.dialect.server_version_info < (4, 1, 0):
            return compiler.process(element.clause, **kw)
        else:
            return compiler.visit_cast(element, **kw)

The above function, which only needs to be declared once
within an application, overrides the compilation of the
:func:`.cast` construct to check for version 4.1.0 before
fully rendering CAST; else the internal element of the
construct is rendered directly.


.. _mysql_indexes:

MySQL Specific Index Options
----------------------------

MySQL-specific extensions to the :class:`.Index` construct are available.

Index Length
~~~~~~~~~~~~~

MySQL provides an option to create index entries with a certain length, where
"length" refers to the number of characters or bytes in each value which will
become part of the index. SQLAlchemy provides this feature via the
``mysql_length`` parameter::

    Index('my_index', my_table.c.data, mysql_length=10)

    Index('a_b_idx', my_table.c.a, my_table.c.b, mysql_length={'a': 4,
                                                               'b': 9})

Prefix lengths are given in characters for nonbinary string types and in bytes
for binary string types. The value passed to the keyword argument *must* be
either an integer (and, thus, specify the same prefix length value for all
columns of the index) or a dict in which keys are column names and values are
prefix length values for corresponding columns. MySQL only allows a length for
a column of an index if it is for a CHAR, VARCHAR, TEXT, BINARY, VARBINARY and
BLOB.

Index Prefixes
~~~~~~~~~~~~~~

MySQL storage engines permit you to specify an index prefix when creating
an index. SQLAlchemy provides this feature via the
``mysql_prefix`` parameter on :class:`.Index`::

    Index('my_index', my_table.c.data, mysql_prefix='FULLTEXT')

The value passed to the keyword argument will be simply passed through to the
underlying CREATE INDEX, so it *must* be a valid index prefix for your MySQL
storage engine.

.. versionadded:: 1.1.5

.. seealso::

    `CREATE INDEX <http://dev.mysql.com/doc/refman/5.0/en/create-index.html>`_ - MySQL documentation

Index Types
~~~~~~~~~~~~~

Some MySQL storage engines permit you to specify an index type when creating
an index or primary key constraint. SQLAlchemy provides this feature via the
``mysql_using`` parameter on :class:`.Index`::

    Index('my_index', my_table.c.data, mysql_using='hash')

As well as the ``mysql_using`` parameter on :class:`.PrimaryKeyConstraint`::

    PrimaryKeyConstraint("data", mysql_using='hash')

The value passed to the keyword argument will be simply passed through to the
underlying CREATE INDEX or PRIMARY KEY clause, so it *must* be a valid index
type for your MySQL storage engine.

More information can be found at:

http://dev.mysql.com/doc/refman/5.0/en/create-index.html

http://dev.mysql.com/doc/refman/5.0/en/create-table.html

Index Parsers
~~~~~~~~~~~~~

CREATE FULLTEXT INDEX in MySQL also supports a "WITH PARSER" option.  This
is available using the keyword argument ``mysql_with_parser``::

    Index(
        'my_index', my_table.c.data,
        mysql_prefix='FULLTEXT', mysql_with_parser="ngram")

.. versionadded:: 1.3


.. _mysql_foreign_keys:

MySQL Foreign Keys
------------------

MySQL's behavior regarding foreign keys has some important caveats.

Foreign Key Arguments to Avoid
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

MySQL does not support the foreign key arguments "DEFERRABLE", "INITIALLY",
or "MATCH".  Using the ``deferrable`` or ``initially`` keyword argument with
:class:`.ForeignKeyConstraint` or :class:`.ForeignKey` will have the effect of
these keywords being rendered in a DDL expression, which will then raise an
error on MySQL.  In order to use these keywords on a foreign key while having
them ignored on a MySQL backend, use a custom compile rule::

    from sqlalchemy.ext.compiler import compiles
    from sqlalchemy.schema import ForeignKeyConstraint

    @compiles(ForeignKeyConstraint, "mysql")
    def process(element, compiler, **kw):
        element.deferrable = element.initially = None
        return compiler.visit_foreign_key_constraint(element, **kw)

.. versionchanged:: 0.9.0 - the MySQL backend no longer silently ignores
   the ``deferrable`` or ``initially`` keyword arguments of
   :class:`.ForeignKeyConstraint` and :class:`.ForeignKey`.

The "MATCH" keyword is in fact more insidious, and is explicitly disallowed
by SQLAlchemy in conjunction with the MySQL backend.  This argument is
silently ignored by MySQL, but in addition has the effect of ON UPDATE and ON
DELETE options also being ignored by the backend.   Therefore MATCH should
never be used with the MySQL backend; as is the case with DEFERRABLE and
INITIALLY, custom compilation rules can be used to correct a MySQL
ForeignKeyConstraint at DDL definition time.

.. versionadded:: 0.9.0 - the MySQL backend will raise a
   :class:`.CompileError` when the ``match`` keyword is used with
   :class:`.ForeignKeyConstraint` or :class:`.ForeignKey`.

Reflection of Foreign Key Constraints
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Not all MySQL storage engines support foreign keys.  When using the
very common ``MyISAM`` MySQL storage engine, the information loaded by table
reflection will not include foreign keys.  For these tables, you may supply a
:class:`~sqlalchemy.ForeignKeyConstraint` at reflection time::

  Table('mytable', metadata,
        ForeignKeyConstraint(['other_id'], ['othertable.other_id']),
        autoload=True
       )

.. seealso::

    :ref:`mysql_storage_engines`

.. _mysql_unique_constraints:

MySQL Unique Constraints and Reflection
---------------------------------------

SQLAlchemy supports both the :class:`.Index` construct with the
flag ``unique=True``, indicating a UNIQUE index, as well as the
:class:`.UniqueConstraint` construct, representing a UNIQUE constraint.
Both objects/syntaxes are supported by MySQL when emitting DDL to create
these constraints.  However, MySQL does not have a unique constraint
construct that is separate from a unique index; that is, the "UNIQUE"
constraint on MySQL is equivalent to creating a "UNIQUE INDEX".

When reflecting these constructs, the :meth:`.Inspector.get_indexes`
and the :meth:`.Inspector.get_unique_constraints` methods will **both**
return an entry for a UNIQUE index in MySQL.  However, when performing
full table reflection using ``Table(..., autoload=True)``,
the :class:`.UniqueConstraint` construct is
**not** part of the fully reflected :class:`.Table` construct under any
circumstances; this construct is always represented by a :class:`.Index`
with the ``unique=True`` setting present in the :attr:`.Table.indexes`
collection.


.. _mysql_timestamp_null:

TIMESTAMP Columns and NULL
--------------------------

MySQL historically enforces that a column which specifies the
TIMESTAMP datatype implicitly includes a default value of
CURRENT_TIMESTAMP, even though this is not stated, and additionally
sets the column as NOT NULL, the opposite behavior vs. that of all
other datatypes::

    mysql> CREATE TABLE ts_test (
        -> a INTEGER,
        -> b INTEGER NOT NULL,
        -> c TIMESTAMP,
        -> d TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        -> e TIMESTAMP NULL);
    Query OK, 0 rows affected (0.03 sec)

    mysql> SHOW CREATE TABLE ts_test;
    +---------+-----------------------------------------------------
    | Table   | Create Table
    +---------+-----------------------------------------------------
    | ts_test | CREATE TABLE `ts_test` (
      `a` int(11) DEFAULT NULL,
      `b` int(11) NOT NULL,
      `c` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      `d` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      `e` timestamp NULL DEFAULT NULL
    ) ENGINE=MyISAM DEFAULT CHARSET=latin1

Above, we see that an INTEGER column defaults to NULL, unless it is specified
with NOT NULL.   But when the column is of type TIMESTAMP, an implicit
default of CURRENT_TIMESTAMP is generated which also coerces the column
to be a NOT NULL, even though we did not specify it as such.

This behavior of MySQL can be changed on the MySQL side using the
`explicit_defaults_for_timestamp
<http://dev.mysql.com/doc/refman/5.6/en/server-system-variables.html
#sysvar_explicit_defaults_for_timestamp>`_ configuration flag introduced in
MySQL 5.6.  With this server setting enabled, TIMESTAMP columns behave like
any other datatype on the MySQL side with regards to defaults and nullability.

However, to accommodate the vast majority of MySQL databases that do not
specify this new flag, SQLAlchemy emits the "NULL" specifier explicitly with
any TIMESTAMP column that does not specify ``nullable=False``.   In order to
accommodate newer databases that specify ``explicit_defaults_for_timestamp``,
SQLAlchemy also emits NOT NULL for TIMESTAMP columns that do specify
``nullable=False``.   The following example illustrates::

    from sqlalchemy import MetaData, Integer, Table, Column, text
    from sqlalchemy.dialects.mysql import TIMESTAMP

    m = MetaData()
    t = Table('ts_test', m,
            Column('a', Integer),
            Column('b', Integer, nullable=False),
            Column('c', TIMESTAMP),
            Column('d', TIMESTAMP, nullable=False)
        )


    from sqlalchemy import create_engine
    e = create_engine("mysql://scott:tiger@localhost/test", echo=True)
    m.create_all(e)

output::

    CREATE TABLE ts_test (
        a INTEGER,
        b INTEGER NOT NULL,
        c TIMESTAMP NULL,
        d TIMESTAMP NOT NULL
    )

.. versionchanged:: 1.0.0 - SQLAlchemy now renders NULL or NOT NULL in all
   cases for TIMESTAMP columns, to accommodate
   ``explicit_defaults_for_timestamp``.  Prior to this version, it will
   not render "NOT NULL" for a TIMESTAMP column that is ``nullable=False``.

"""  # noqa

from array import array as _array
from collections import defaultdict
import re
import sys

from . import reflection as _reflection
from .enumerated import ENUM
from .enumerated import SET
from .json import JSON
from .json import JSONIndexType
from .json import JSONPathType
from .types import _FloatType
from .types import _IntegerType
from .types import _MatchType
from .types import _NumericType
from .types import _StringType
from .types import BIGINT
from .types import BIT
from .types import CHAR
from .types import DATETIME
from .types import DECIMAL
from .types import DOUBLE
from .types import FLOAT
from .types import INTEGER
from .types import LONGBLOB
from .types import LONGTEXT
from .types import MEDIUMBLOB
from .types import MEDIUMINT
from .types import MEDIUMTEXT
from .types import NCHAR
from .types import NUMERIC
from .types import NVARCHAR
from .types import REAL
from .types import SMALLINT
from .types import TEXT
from .types import TIME
from .types import TIMESTAMP
from .types import TINYBLOB
from .types import TINYINT
from .types import TINYTEXT
from .types import VARCHAR
from .types import YEAR
from ... import exc
from ... import log
from ... import schema as sa_schema
from ... import sql
from ... import types as sqltypes
from ... import util
from ...engine import default
from ...engine import reflection
from ...sql import coercions
from ...sql import compiler
from ...sql import elements
from ...sql import roles
from ...types import BINARY
from ...types import BLOB
from ...types import BOOLEAN
from ...types import DATE
from ...types import VARBINARY
from ...util import topological


RESERVED_WORDS = set(
    [
        "accessible",
        "add",
        "all",
        "alter",
        "analyze",
        "and",
        "as",
        "asc",
        "asensitive",
        "before",
        "between",
        "bigint",
        "binary",
        "blob",
        "both",
        "by",
        "call",
        "cascade",
        "case",
        "change",
        "char",
        "character",
        "check",
        "collate",
        "column",
        "condition",
        "constraint",
        "continue",
        "convert",
        "create",
        "cross",
        "current_date",
        "current_time",
        "current_timestamp",
        "current_user",
        "cursor",
        "database",
        "databases",
        "day_hour",
        "day_microsecond",
        "day_minute",
        "day_second",
        "dec",
        "decimal",
        "declare",
        "default",
        "delayed",
        "delete",
        "desc",
        "describe",
        "deterministic",
        "distinct",
        "distinctrow",
        "div",
        "double",
        "drop",
        "dual",
        "each",
        "else",
        "elseif",
        "enclosed",
        "escaped",
        "exists",
        "exit",
        "explain",
        "false",
        "fetch",
        "float",
        "float4",
        "float8",
        "for",
        "force",
        "foreign",
        "from",
        "fulltext",
        "grant",
        "group",
        "having",
        "high_priority",
        "hour_microsecond",
        "hour_minute",
        "hour_second",
        "if",
        "ignore",
        "in",
        "index",
        "infile",
        "inner",
        "inout",
        "insensitive",
        "insert",
        "int",
        "int1",
        "int2",
        "int3",
        "int4",
        "int8",
        "integer",
        "interval",
        "into",
        "is",
        "iterate",
        "join",
        "key",
        "keys",
        "kill",
        "leading",
        "leave",
        "left",
        "like",
        "limit",
        "linear",
        "lines",
        "load",
        "localtime",
        "localtimestamp",
        "lock",
        "long",
        "longblob",
        "longtext",
        "loop",
        "low_priority",
        "master_ssl_verify_server_cert",
        "match",
        "mediumblob",
        "mediumint",
        "mediumtext",
        "middleint",
        "minute_microsecond",
        "minute_second",
        "mod",
        "modifies",
        "natural",
        "not",
        "no_write_to_binlog",
        "null",
        "numeric",
        "on",
        "optimize",
        "option",
        "optionally",
        "or",
        "order",
        "out",
        "outer",
        "outfile",
        "precision",
        "primary",
        "procedure",
        "purge",
        "range",
        "read",
        "reads",
        "read_only",
        "read_write",
        "real",
        "references",
        "regexp",
        "release",
        "rename",
        "repeat",
        "replace",
        "require",
        "restrict",
        "return",
        "revoke",
        "right",
        "rlike",
        "schema",
        "schemas",
        "second_microsecond",
        "select",
        "sensitive",
        "separator",
        "set",
        "show",
        "smallint",
        "spatial",
        "specific",
        "sql",
        "sqlexception",
        "sqlstate",
        "sqlwarning",
        "sql_big_result",
        "sql_calc_found_rows",
        "sql_small_result",
        "ssl",
        "starting",
        "straight_join",
        "table",
        "terminated",
        "then",
        "tinyblob",
        "tinyint",
        "tinytext",
        "to",
        "trailing",
        "trigger",
        "true",
        "undo",
        "union",
        "unique",
        "unlock",
        "unsigned",
        "update",
        "usage",
        "use",
        "using",
        "utc_date",
        "utc_time",
        "utc_timestamp",
        "values",
        "varbinary",
        "varchar",
        "varcharacter",
        "varying",
        "when",
        "where",
        "while",
        "with",
        "write",
        "x509",
        "xor",
        "year_month",
        "zerofill",  # 5.0
        "columns",
        "fields",
        "privileges",
        "soname",
        "tables",  # 4.1
        "accessible",
        "linear",
        "master_ssl_verify_server_cert",
        "range",
        "read_only",
        "read_write",  # 5.1
        "general",
        "ignore_server_ids",
        "master_heartbeat_period",
        "maxvalue",
        "resignal",
        "signal",
        "slow",  # 5.5
        "get",
        "io_after_gtids",
        "io_before_gtids",
        "master_bind",
        "one_shot",
        "partition",
        "sql_after_gtids",
        "sql_before_gtids",  # 5.6
        "generated",
        "optimizer_costs",
        "stored",
        "virtual",  # 5.7
        "admin",
        "cume_dist",
        "empty",
        "except",
        "first_value",
        "grouping",
        "function",
        "groups",
        "json_table",
        "last_value",
        "nth_value",
        "ntile",
        "of",
        "over",
        "percent_rank",
        "persist",
        "persist_only",
        "rank",
        "recursive",
        "role",
        "row",
        "rows",
        "row_number",
        "system",
        "window",  # 8.0
    ]
)

AUTOCOMMIT_RE = re.compile(
    r"\s*(?:UPDATE|INSERT|CREATE|DELETE|DROP|ALTER|LOAD +DATA|REPLACE)",
    re.I | re.UNICODE,
)
SET_RE = re.compile(
    r"\s*SET\s+(?:(?:GLOBAL|SESSION)\s+)?\w", re.I | re.UNICODE
)


# old names
MSTime = TIME
MSSet = SET
MSEnum = ENUM
MSLongBlob = LONGBLOB
MSMediumBlob = MEDIUMBLOB
MSTinyBlob = TINYBLOB
MSBlob = BLOB
MSBinary = BINARY
MSVarBinary = VARBINARY
MSNChar = NCHAR
MSNVarChar = NVARCHAR
MSChar = CHAR
MSString = VARCHAR
MSLongText = LONGTEXT
MSMediumText = MEDIUMTEXT
MSTinyText = TINYTEXT
MSText = TEXT
MSYear = YEAR
MSTimeStamp = TIMESTAMP
MSBit = BIT
MSSmallInteger = SMALLINT
MSTinyInteger = TINYINT
MSMediumInteger = MEDIUMINT
MSBigInteger = BIGINT
MSNumeric = NUMERIC
MSDecimal = DECIMAL
MSDouble = DOUBLE
MSReal = REAL
MSFloat = FLOAT
MSInteger = INTEGER

colspecs = {
    _IntegerType: _IntegerType,
    _NumericType: _NumericType,
    _FloatType: _FloatType,
    sqltypes.Numeric: NUMERIC,
    sqltypes.Float: FLOAT,
    sqltypes.Time: TIME,
    sqltypes.Enum: ENUM,
    sqltypes.MatchType: _MatchType,
    sqltypes.JSON: JSON,
    sqltypes.JSON.JSONIndexType: JSONIndexType,
    sqltypes.JSON.JSONPathType: JSONPathType,
}

# Everything 3.23 through 5.1 excepting OpenGIS types.
ischema_names = {
    "bigint": BIGINT,
    "binary": BINARY,
    "bit": BIT,
    "blob": BLOB,
    "boolean": BOOLEAN,
    "char": CHAR,
    "date": DATE,
    "datetime": DATETIME,
    "decimal": DECIMAL,
    "double": DOUBLE,
    "enum": ENUM,
    "fixed": DECIMAL,
    "float": FLOAT,
    "int": INTEGER,
    "integer": INTEGER,
    "json": JSON,
    "longblob": LONGBLOB,
    "longtext": LONGTEXT,
    "mediumblob": MEDIUMBLOB,
    "mediumint": MEDIUMINT,
    "mediumtext": MEDIUMTEXT,
    "nchar": NCHAR,
    "nvarchar": NVARCHAR,
    "numeric": NUMERIC,
    "set": SET,
    "smallint": SMALLINT,
    "text": TEXT,
    "time": TIME,
    "timestamp": TIMESTAMP,
    "tinyblob": TINYBLOB,
    "tinyint": TINYINT,
    "tinytext": TINYTEXT,
    "varbinary": VARBINARY,
    "varchar": VARCHAR,
    "year": YEAR,
}


class MySQLExecutionContext(default.DefaultExecutionContext):
    def should_autocommit_text(self, statement):
        return AUTOCOMMIT_RE.match(statement)

    def create_server_side_cursor(self):
        if self.dialect.supports_server_side_cursors:
            return self._dbapi_connection.cursor(self.dialect._sscursor)
        else:
            raise NotImplementedError()


class MySQLCompiler(compiler.SQLCompiler):

    render_table_with_column_in_update_from = True
    """Overridden from base SQLCompiler value"""

    extract_map = compiler.SQLCompiler.extract_map.copy()
    extract_map.update({"milliseconds": "millisecond"})

    def visit_random_func(self, fn, **kw):
        return "rand%s" % self.function_argspec(fn)

    def visit_sysdate_func(self, fn, **kw):
        return "SYSDATE()"

    def visit_json_getitem_op_binary(self, binary, operator, **kw):
        return "JSON_EXTRACT(%s, %s)" % (
            self.process(binary.left, **kw),
            self.process(binary.right, **kw),
        )

    def visit_json_path_getitem_op_binary(self, binary, operator, **kw):
        return "JSON_EXTRACT(%s, %s)" % (
            self.process(binary.left, **kw),
            self.process(binary.right, **kw),
        )

    def visit_on_duplicate_key_update(self, on_duplicate, **kw):
        if on_duplicate._parameter_ordering:
            parameter_ordering = [
                coercions.expect(roles.DMLColumnRole, key)
                for key in on_duplicate._parameter_ordering
            ]
            ordered_keys = set(parameter_ordering)
            cols = [
                self.statement.table.c[key]
                for key in parameter_ordering
                if key in self.statement.table.c
            ] + [
                c for c in self.statement.table.c if c.key not in ordered_keys
            ]
        else:
            cols = self.statement.table.c

        clauses = []
        # traverses through all table columns to preserve table column order
        for column in (col for col in cols if col.key in on_duplicate.update):

            val = on_duplicate.update[column.key]

            if coercions._is_literal(val):
                val = elements.BindParameter(None, val, type_=column.type)
                value_text = self.process(val.self_group(), use_schema=False)
            elif isinstance(val, elements.BindParameter) and val.type._isnull:
                val = val._clone()
                val.type = column.type
                value_text = self.process(val.self_group(), use_schema=False)
            elif (
                isinstance(val, elements.ColumnClause)
                and val.table is on_duplicate.inserted_alias
            ):
                value_text = "VALUES(" + self.preparer.quote(column.name) + ")"
            else:
                value_text = self.process(val.self_group(), use_schema=False)
            name_text = self.preparer.quote(column.name)
            clauses.append("%s = %s" % (name_text, value_text))

        non_matching = set(on_duplicate.update) - set(c.key for c in cols)
        if non_matching:
            util.warn(
                "Additional column names not matching "
                "any column keys in table '%s': %s"
                % (
                    self.statement.table.name,
                    (", ".join("'%s'" % c for c in non_matching)),
                )
            )

        return "ON DUPLICATE KEY UPDATE " + ", ".join(clauses)

    def visit_concat_op_binary(self, binary, operator, **kw):
        return "concat(%s, %s)" % (
            self.process(binary.left, **kw),
            self.process(binary.right, **kw),
        )

    def visit_match_op_binary(self, binary, operator, **kw):
        return "MATCH (%s) AGAINST (%s IN BOOLEAN MODE)" % (
            self.process(binary.left, **kw),
            self.process(binary.right, **kw),
        )

    def get_from_hint_text(self, table, text):
        return text

    def visit_typeclause(self, typeclause, type_=None, **kw):
        if type_ is None:
            type_ = typeclause.type.dialect_impl(self.dialect)
        if isinstance(type_, sqltypes.TypeDecorator):
            return self.visit_typeclause(typeclause, type_.impl, **kw)
        elif isinstance(type_, sqltypes.Integer):
            if getattr(type_, "unsigned", False):
                return "UNSIGNED INTEGER"
            else:
                return "SIGNED INTEGER"
        elif isinstance(type_, sqltypes.TIMESTAMP):
            return "DATETIME"
        elif isinstance(
            type_,
            (
                sqltypes.DECIMAL,
                sqltypes.DateTime,
                sqltypes.Date,
                sqltypes.Time,
            ),
        ):
            return self.dialect.type_compiler.process(type_)
        elif isinstance(type_, sqltypes.String) and not isinstance(
            type_, (ENUM, SET)
        ):
            adapted = CHAR._adapt_string_for_cast(type_)
            return self.dialect.type_compiler.process(adapted)
        elif isinstance(type_, sqltypes._Binary):
            return "BINARY"
        elif isinstance(type_, sqltypes.JSON):
            return "JSON"
        elif isinstance(type_, sqltypes.NUMERIC):
            return self.dialect.type_compiler.process(type_).replace(
                "NUMERIC", "DECIMAL"
            )
        else:
            return None

    def visit_cast(self, cast, **kw):
        # No cast until 4, no decimals until 5.
        if not self.dialect._supports_cast:
            util.warn(
                "Current MySQL version does not support "
                "CAST; the CAST will be skipped."
            )
            return self.process(cast.clause.self_group(), **kw)

        type_ = self.process(cast.typeclause)
        if type_ is None:
            util.warn(
                "Datatype %s does not support CAST on MySQL; "
                "the CAST will be skipped."
                % self.dialect.type_compiler.process(cast.typeclause.type)
            )
            return self.process(cast.clause.self_group(), **kw)

        return "CAST(%s AS %s)" % (self.process(cast.clause, **kw), type_)

    def render_literal_value(self, value, type_):
        value = super(MySQLCompiler, self).render_literal_value(value, type_)
        if self.dialect._backslash_escapes:
            value = value.replace("\\", "\\\\")
        return value

    # override native_boolean=False behavior here, as
    # MySQL still supports native boolean
    def visit_true(self, element, **kw):
        return "true"

    def visit_false(self, element, **kw):
        return "false"

    def get_select_precolumns(self, select, **kw):
        """Add special MySQL keywords in place of DISTINCT.

        .. note::

          this usage is deprecated.  :meth:`.Select.prefix_with`
          should be used for special keywords at the start
          of a SELECT.

        """
        if isinstance(select._distinct, util.string_types):
            return select._distinct.upper() + " "
        elif select._distinct:
            return "DISTINCT "
        else:
            return ""

    def visit_join(self, join, asfrom=False, **kwargs):
        if join.full:
            join_type = " FULL OUTER JOIN "
        elif join.isouter:
            join_type = " LEFT OUTER JOIN "
        else:
            join_type = " INNER JOIN "

        return "".join(
            (
                self.process(join.left, asfrom=True, **kwargs),
                join_type,
                self.process(join.right, asfrom=True, **kwargs),
                " ON ",
                self.process(join.onclause, **kwargs),
            )
        )

    def for_update_clause(self, select, **kw):
        if select._for_update_arg.read:
            return " LOCK IN SHARE MODE"
        else:
            return " FOR UPDATE"

    def limit_clause(self, select, **kw):
        # MySQL supports:
        #   LIMIT <limit>
        #   LIMIT <offset>, <limit>
        # and in server versions > 3.3:
        #   LIMIT <limit> OFFSET <offset>
        # The latter is more readable for offsets but we're stuck with the
        # former until we can refine dialects by server revision.

        limit_clause, offset_clause = (
            select._limit_clause,
            select._offset_clause,
        )

        if limit_clause is None and offset_clause is None:
            return ""
        elif offset_clause is not None:
            # As suggested by the MySQL docs, need to apply an
            # artificial limit if one wasn't provided
            # http://dev.mysql.com/doc/refman/5.0/en/select.html
            if limit_clause is None:
                # hardwire the upper limit.  Currently
                # needed by OurSQL with Python 3
                # (https://bugs.launchpad.net/oursql/+bug/686232),
                # but also is consistent with the usage of the upper
                # bound as part of MySQL's "syntax" for OFFSET with
                # no LIMIT
                return " \n LIMIT %s, %s" % (
                    self.process(offset_clause, **kw),
                    "18446744073709551615",
                )
            else:
                return " \n LIMIT %s, %s" % (
                    self.process(offset_clause, **kw),
                    self.process(limit_clause, **kw),
                )
        else:
            # No offset provided, so just use the limit
            return " \n LIMIT %s" % (self.process(limit_clause, **kw),)

    def update_limit_clause(self, update_stmt):
        limit = update_stmt.kwargs.get("%s_limit" % self.dialect.name, None)
        if limit:
            return "LIMIT %s" % limit
        else:
            return None

    def update_tables_clause(self, update_stmt, from_table, extra_froms, **kw):
        return ", ".join(
            t._compiler_dispatch(self, asfrom=True, **kw)
            for t in [from_table] + list(extra_froms)
        )

    def update_from_clause(
        self, update_stmt, from_table, extra_froms, from_hints, **kw
    ):
        return None

    def delete_table_clause(self, delete_stmt, from_table, extra_froms):
        """If we have extra froms make sure we render any alias as hint."""
        ashint = False
        if extra_froms:
            ashint = True
        return from_table._compiler_dispatch(
            self, asfrom=True, iscrud=True, ashint=ashint
        )

    def delete_extra_from_clause(
        self, delete_stmt, from_table, extra_froms, from_hints, **kw
    ):
        """Render the DELETE .. USING clause specific to MySQL."""
        return "USING " + ", ".join(
            t._compiler_dispatch(self, asfrom=True, fromhints=from_hints, **kw)
            for t in [from_table] + extra_froms
        )

    def visit_empty_set_expr(self, element_types):
        return (
            "SELECT %(outer)s FROM (SELECT %(inner)s) "
            "as _empty_set WHERE 1!=1"
            % {
                "inner": ", ".join(
                    "1 AS _in_%s" % idx
                    for idx, type_ in enumerate(element_types)
                ),
                "outer": ", ".join(
                    "_in_%s" % idx for idx, type_ in enumerate(element_types)
                ),
            }
        )


class MySQLDDLCompiler(compiler.DDLCompiler):
    def get_column_specification(self, column, **kw):
        """Builds column DDL."""

        colspec = [
            self.preparer.format_column(column),
            self.dialect.type_compiler.process(
                column.type, type_expression=column
            ),
        ]

        is_timestamp = isinstance(column.type, sqltypes.TIMESTAMP)

        if not column.nullable:
            colspec.append("NOT NULL")

        # see: http://docs.sqlalchemy.org/en/latest/dialects/
        #   mysql.html#mysql_timestamp_null
        elif column.nullable and is_timestamp:
            colspec.append("NULL")

        default = self.get_column_default_string(column)
        if default is not None:
            colspec.append("DEFAULT " + default)

        comment = column.comment
        if comment is not None:
            literal = self.sql_compiler.render_literal_value(
                comment, sqltypes.String()
            )
            colspec.append("COMMENT " + literal)

        if (
            column.table is not None
            and column is column.table._autoincrement_column
            and column.server_default is None
        ):
            colspec.append("AUTO_INCREMENT")

        return " ".join(colspec)

    def post_create_table(self, table):
        """Build table-level CREATE options like ENGINE and COLLATE."""

        table_opts = []

        opts = dict(
            (k[len(self.dialect.name) + 1 :].upper(), v)
            for k, v in table.kwargs.items()
            if k.startswith("%s_" % self.dialect.name)
        )

        if table.comment is not None:
            opts["COMMENT"] = table.comment

        partition_options = [
            "PARTITION_BY",
            "PARTITIONS",
            "SUBPARTITIONS",
            "SUBPARTITION_BY",
        ]

        nonpart_options = set(opts).difference(partition_options)
        part_options = set(opts).intersection(partition_options)

        for opt in topological.sort(
            [
                ("DEFAULT_CHARSET", "COLLATE"),
                ("DEFAULT_CHARACTER_SET", "COLLATE"),
            ],
            nonpart_options,
        ):
            arg = opts[opt]
            if opt in _reflection._options_of_type_string:

                arg = self.sql_compiler.render_literal_value(
                    arg, sqltypes.String()
                )

            if opt in (
                "DATA_DIRECTORY",
                "INDEX_DIRECTORY",
                "DEFAULT_CHARACTER_SET",
                "CHARACTER_SET",
                "DEFAULT_CHARSET",
                "DEFAULT_COLLATE",
            ):
                opt = opt.replace("_", " ")

            joiner = "="
            if opt in (
                "TABLESPACE",
                "DEFAULT CHARACTER SET",
                "CHARACTER SET",
                "COLLATE",
            ):
                joiner = " "

            table_opts.append(joiner.join((opt, arg)))

        for opt in topological.sort(
            [
                ("PARTITION_BY", "PARTITIONS"),
                ("PARTITION_BY", "SUBPARTITION_BY"),
                ("PARTITION_BY", "SUBPARTITIONS"),
                ("PARTITIONS", "SUBPARTITIONS"),
                ("PARTITIONS", "SUBPARTITION_BY"),
                ("SUBPARTITION_BY", "SUBPARTITIONS"),
            ],
            part_options,
        ):
            arg = opts[opt]
            if opt in _reflection._options_of_type_string:
                arg = self.sql_compiler.render_literal_value(
                    arg, sqltypes.String()
                )

            opt = opt.replace("_", " ")
            joiner = " "

            table_opts.append(joiner.join((opt, arg)))

        return " ".join(table_opts)

    def visit_create_index(self, create, **kw):
        index = create.element
        self._verify_index_table(index)
        preparer = self.preparer
        table = preparer.format_table(index.table)
        columns = [
            self.sql_compiler.process(
                expr, include_table=False, literal_binds=True
            )
            for expr in index.expressions
        ]

        name = self._prepared_index_name(index)

        text = "CREATE "
        if index.unique:
            text += "UNIQUE "

        index_prefix = index.kwargs.get("mysql_prefix", None)
        if index_prefix:
            text += index_prefix + " "

        text += "INDEX %s ON %s " % (name, table)

        length = index.dialect_options["mysql"]["length"]
        if length is not None:

            if isinstance(length, dict):
                # length value can be a (column_name --> integer value)
                # mapping specifying the prefix length for each column of the
                # index
                columns = ", ".join(
                    "%s(%d)" % (expr, length[col.name])
                    if col.name in length
                    else (
                        "%s(%d)" % (expr, length[expr])
                        if expr in length
                        else "%s" % expr
                    )
                    for col, expr in zip(index.expressions, columns)
                )
            else:
                # or can be an integer value specifying the same
                # prefix length for all columns of the index
                columns = ", ".join(
                    "%s(%d)" % (col, length) for col in columns
                )
        else:
            columns = ", ".join(columns)
        text += "(%s)" % columns

        parser = index.dialect_options["mysql"]["with_parser"]
        if parser is not None:
            text += " WITH PARSER %s" % (parser,)

        using = index.dialect_options["mysql"]["using"]
        if using is not None:
            text += " USING %s" % (preparer.quote(using))

        return text

    def visit_primary_key_constraint(self, constraint):
        text = super(MySQLDDLCompiler, self).visit_primary_key_constraint(
            constraint
        )
        using = constraint.dialect_options["mysql"]["using"]
        if using:
            text += " USING %s" % (self.preparer.quote(using))
        return text

    def visit_drop_index(self, drop):
        index = drop.element

        return "\nDROP INDEX %s ON %s" % (
            self._prepared_index_name(index, include_schema=False),
            self.preparer.format_table(index.table),
        )

    def visit_drop_constraint(self, drop):
        constraint = drop.element
        if isinstance(constraint, sa_schema.ForeignKeyConstraint):
            qual = "FOREIGN KEY "
            const = self.preparer.format_constraint(constraint)
        elif isinstance(constraint, sa_schema.PrimaryKeyConstraint):
            qual = "PRIMARY KEY "
            const = ""
        elif isinstance(constraint, sa_schema.UniqueConstraint):
            qual = "INDEX "
            const = self.preparer.format_constraint(constraint)
        elif isinstance(constraint, sa_schema.CheckConstraint):
            if self.dialect._is_mariadb:
                qual = "CONSTRAINT "
            else:
                qual = "CHECK "
            const = self.preparer.format_constraint(constraint)
        else:
            qual = ""
            const = self.preparer.format_constraint(constraint)
        return "ALTER TABLE %s DROP %s%s" % (
            self.preparer.format_table(constraint.table),
            qual,
            const,
        )

    def define_constraint_match(self, constraint):
        if constraint.match is not None:
            raise exc.CompileError(
                "MySQL ignores the 'MATCH' keyword while at the same time "
                "causes ON UPDATE/ON DELETE clauses to be ignored."
            )
        return ""

    def visit_set_table_comment(self, create):
        return "ALTER TABLE %s COMMENT %s" % (
            self.preparer.format_table(create.element),
            self.sql_compiler.render_literal_value(
                create.element.comment, sqltypes.String()
            ),
        )

    def visit_drop_table_comment(self, create):
        return "ALTER TABLE %s COMMENT ''" % (
            self.preparer.format_table(create.element)
        )

    def visit_set_column_comment(self, create):
        return "ALTER TABLE %s CHANGE %s %s" % (
            self.preparer.format_table(create.element.table),
            self.preparer.format_column(create.element),
            self.get_column_specification(create.element),
        )


class MySQLTypeCompiler(compiler.GenericTypeCompiler):
    def _extend_numeric(self, type_, spec):
        "Extend a numeric-type declaration with MySQL specific extensions."

        if not self._mysql_type(type_):
            return spec

        if type_.unsigned:
            spec += " UNSIGNED"
        if type_.zerofill:
            spec += " ZEROFILL"
        return spec

    def _extend_string(self, type_, defaults, spec):
        """Extend a string-type declaration with standard SQL CHARACTER SET /
        COLLATE annotations and MySQL specific extensions.

        """

        def attr(name):
            return getattr(type_, name, defaults.get(name))

        if attr("charset"):
            charset = "CHARACTER SET %s" % attr("charset")
        elif attr("ascii"):
            charset = "ASCII"
        elif attr("unicode"):
            charset = "UNICODE"
        else:
            charset = None

        if attr("collation"):
            collation = "COLLATE %s" % type_.collation
        elif attr("binary"):
            collation = "BINARY"
        else:
            collation = None

        if attr("national"):
            # NATIONAL (aka NCHAR/NVARCHAR) trumps charsets.
            return " ".join(
                [c for c in ("NATIONAL", spec, collation) if c is not None]
            )
        return " ".join(
            [c for c in (spec, charset, collation) if c is not None]
        )

    def _mysql_type(self, type_):
        return isinstance(type_, (_StringType, _NumericType))

    def visit_NUMERIC(self, type_, **kw):
        if type_.precision is None:
            return self._extend_numeric(type_, "NUMERIC")
        elif type_.scale is None:
            return self._extend_numeric(
                type_,
                "NUMERIC(%(precision)s)" % {"precision": type_.precision},
            )
        else:
            return self._extend_numeric(
                type_,
                "NUMERIC(%(precision)s, %(scale)s)"
                % {"precision": type_.precision, "scale": type_.scale},
            )

    def visit_DECIMAL(self, type_, **kw):
        if type_.precision is None:
            return self._extend_numeric(type_, "DECIMAL")
        elif type_.scale is None:
            return self._extend_numeric(
                type_,
                "DECIMAL(%(precision)s)" % {"precision": type_.precision},
            )
        else:
            return self._extend_numeric(
                type_,
                "DECIMAL(%(precision)s, %(scale)s)"
                % {"precision": type_.precision, "scale": type_.scale},
            )

    def visit_DOUBLE(self, type_, **kw):
        if type_.precision is not None and type_.scale is not None:
            return self._extend_numeric(
                type_,
                "DOUBLE(%(precision)s, %(scale)s)"
                % {"precision": type_.precision, "scale": type_.scale},
            )
        else:
            return self._extend_numeric(type_, "DOUBLE")

    def visit_REAL(self, type_, **kw):
        if type_.precision is not None and type_.scale is not None:
            return self._extend_numeric(
                type_,
                "REAL(%(precision)s, %(scale)s)"
                % {"precision": type_.precision, "scale": type_.scale},
            )
        else:
            return self._extend_numeric(type_, "REAL")

    def visit_FLOAT(self, type_, **kw):
        if (
            self._mysql_type(type_)
            and type_.scale is not None
            and type_.precision is not None
        ):
            return self._extend_numeric(
                type_, "FLOAT(%s, %s)" % (type_.precision, type_.scale)
            )
        elif type_.precision is not None:
            return self._extend_numeric(
                type_, "FLOAT(%s)" % (type_.precision,)
            )
        else:
            return self._extend_numeric(type_, "FLOAT")

    def visit_INTEGER(self, type_, **kw):
        if self._mysql_type(type_) and type_.display_width is not None:
            return self._extend_numeric(
                type_,
                "INTEGER(%(display_width)s)"
                % {"display_width": type_.display_width},
            )
        else:
            return self._extend_numeric(type_, "INTEGER")

    def visit_BIGINT(self, type_, **kw):
        if self._mysql_type(type_) and type_.display_width is not None:
            return self._extend_numeric(
                type_,
                "BIGINT(%(display_width)s)"
                % {"display_width": type_.display_width},
            )
        else:
            return self._extend_numeric(type_, "BIGINT")

    def visit_MEDIUMINT(self, type_, **kw):
        if self._mysql_type(type_) and type_.display_width is not None:
            return self._extend_numeric(
                type_,
                "MEDIUMINT(%(display_width)s)"
                % {"display_width": type_.display_width},
            )
        else:
            return self._extend_numeric(type_, "MEDIUMINT")

    def visit_TINYINT(self, type_, **kw):
        if self._mysql_type(type_) and type_.display_width is not None:
            return self._extend_numeric(
                type_, "TINYINT(%s)" % type_.display_width
            )
        else:
            return self._extend_numeric(type_, "TINYINT")

    def visit_SMALLINT(self, type_, **kw):
        if self._mysql_type(type_) and type_.display_width is not None:
            return self._extend_numeric(
                type_,
                "SMALLINT(%(display_width)s)"
                % {"display_width": type_.display_width},
            )
        else:
            return self._extend_numeric(type_, "SMALLINT")

    def visit_BIT(self, type_, **kw):
        if type_.length is not None:
            return "BIT(%s)" % type_.length
        else:
            return "BIT"

    def visit_DATETIME(self, type_, **kw):
        if getattr(type_, "fsp", None):
            return "DATETIME(%d)" % type_.fsp
        else:
            return "DATETIME"

    def visit_DATE(self, type_, **kw):
        return "DATE"

    def visit_TIME(self, type_, **kw):
        if getattr(type_, "fsp", None):
            return "TIME(%d)" % type_.fsp
        else:
            return "TIME"

    def visit_TIMESTAMP(self, type_, **kw):
        if getattr(type_, "fsp", None):
            return "TIMESTAMP(%d)" % type_.fsp
        else:
            return "TIMESTAMP"

    def visit_YEAR(self, type_, **kw):
        if type_.display_width is None:
            return "YEAR"
        else:
            return "YEAR(%s)" % type_.display_width

    def visit_TEXT(self, type_, **kw):
        if type_.length:
            return self._extend_string(type_, {}, "TEXT(%d)" % type_.length)
        else:
            return self._extend_string(type_, {}, "TEXT")

    def visit_TINYTEXT(self, type_, **kw):
        return self._extend_string(type_, {}, "TINYTEXT")

    def visit_MEDIUMTEXT(self, type_, **kw):
        return self._extend_string(type_, {}, "MEDIUMTEXT")

    def visit_LONGTEXT(self, type_, **kw):
        return self._extend_string(type_, {}, "LONGTEXT")

    def visit_VARCHAR(self, type_, **kw):
        if type_.length:
            return self._extend_string(type_, {}, "VARCHAR(%d)" % type_.length)
        else:
            raise exc.CompileError(
                "VARCHAR requires a length on dialect %s" % self.dialect.name
            )

    def visit_CHAR(self, type_, **kw):
        if type_.length:
            return self._extend_string(
                type_, {}, "CHAR(%(length)s)" % {"length": type_.length}
            )
        else:
            return self._extend_string(type_, {}, "CHAR")

    def visit_NVARCHAR(self, type_, **kw):
        # We'll actually generate the equiv. "NATIONAL VARCHAR" instead
        # of "NVARCHAR".
        if type_.length:
            return self._extend_string(
                type_,
                {"national": True},
                "VARCHAR(%(length)s)" % {"length": type_.length},
            )
        else:
            raise exc.CompileError(
                "NVARCHAR requires a length on dialect %s" % self.dialect.name
            )

    def visit_NCHAR(self, type_, **kw):
        # We'll actually generate the equiv.
        # "NATIONAL CHAR" instead of "NCHAR".
        if type_.length:
            return self._extend_string(
                type_,
                {"national": True},
                "CHAR(%(length)s)" % {"length": type_.length},
            )
        else:
            return self._extend_string(type_, {"national": True}, "CHAR")

    def visit_VARBINARY(self, type_, **kw):
        return "VARBINARY(%d)" % type_.length

    def visit_JSON(self, type_, **kw):
        return "JSON"

    def visit_large_binary(self, type_, **kw):
        return self.visit_BLOB(type_)

    def visit_enum(self, type_, **kw):
        if not type_.native_enum:
            return super(MySQLTypeCompiler, self).visit_enum(type_)
        else:
            return self._visit_enumerated_values("ENUM", type_, type_.enums)

    def visit_BLOB(self, type_, **kw):
        if type_.length:
            return "BLOB(%d)" % type_.length
        else:
            return "BLOB"

    def visit_TINYBLOB(self, type_, **kw):
        return "TINYBLOB"

    def visit_MEDIUMBLOB(self, type_, **kw):
        return "MEDIUMBLOB"

    def visit_LONGBLOB(self, type_, **kw):
        return "LONGBLOB"

    def _visit_enumerated_values(self, name, type_, enumerated_values):
        quoted_enums = []
        for e in enumerated_values:
            quoted_enums.append("'%s'" % e.replace("'", "''"))
        return self._extend_string(
            type_, {}, "%s(%s)" % (name, ",".join(quoted_enums))
        )

    def visit_ENUM(self, type_, **kw):
        return self._visit_enumerated_values(
            "ENUM", type_, type_._enumerated_values
        )

    def visit_SET(self, type_, **kw):
        return self._visit_enumerated_values(
            "SET", type_, type_._enumerated_values
        )

    def visit_BOOLEAN(self, type_, **kw):
        return "BOOL"


class MySQLIdentifierPreparer(compiler.IdentifierPreparer):

    reserved_words = RESERVED_WORDS

    def __init__(self, dialect, server_ansiquotes=False, **kw):
        if not server_ansiquotes:
            quote = "`"
        else:
            quote = '"'

        super(MySQLIdentifierPreparer, self).__init__(
            dialect, initial_quote=quote, escape_quote=quote
        )

    def _quote_free_identifiers(self, *ids):
        """Unilaterally identifier-quote any number of strings."""

        return tuple([self.quote_identifier(i) for i in ids if i is not None])


@log.class_logger
class MySQLDialect(default.DefaultDialect):
    """Details of the MySQL dialect.
    Not used directly in application code.
    """

    name = "mysql"
    supports_alter = True

    # MySQL has no true "boolean" type; we
    # allow for the "true" and "false" keywords, however
    supports_native_boolean = False

    # identifiers are 64, however aliases can be 255...
    max_identifier_length = 255
    max_index_name_length = 64

    supports_native_enum = True

    supports_sane_rowcount = True
    supports_sane_multi_rowcount = False
    supports_multivalues_insert = True

    supports_comments = True
    inline_comments = True
    default_paramstyle = "format"
    colspecs = colspecs

    cte_follows_insert = True

    statement_compiler = MySQLCompiler
    ddl_compiler = MySQLDDLCompiler
    type_compiler = MySQLTypeCompiler
    ischema_names = ischema_names
    preparer = MySQLIdentifierPreparer

    # default SQL compilation settings -
    # these are modified upon initialize(),
    # i.e. first connect
    _backslash_escapes = True
    _server_ansiquotes = False

    construct_arguments = [
        (sa_schema.Table, {"*": None}),
        (sql.Update, {"limit": None}),
        (sa_schema.PrimaryKeyConstraint, {"using": None}),
        (
            sa_schema.Index,
            {
                "using": None,
                "length": None,
                "prefix": None,
                "with_parser": None,
            },
        ),
    ]

    def __init__(
        self,
        isolation_level=None,
        json_serializer=None,
        json_deserializer=None,
        **kwargs
    ):
        kwargs.pop("use_ansiquotes", None)  # legacy
        default.DefaultDialect.__init__(self, **kwargs)
        self.isolation_level = isolation_level
        self._json_serializer = json_serializer
        self._json_deserializer = json_deserializer

    def on_connect(self):
        if self.isolation_level is not None:

            def connect(conn):
                self.set_isolation_level(conn, self.isolation_level)

            return connect
        else:
            return None

    _isolation_lookup = set(
        [
            "SERIALIZABLE",
            "READ UNCOMMITTED",
            "READ COMMITTED",
            "REPEATABLE READ",
        ]
    )

    def set_isolation_level(self, connection, level):
        level = level.replace("_", " ")

        # adjust for ConnectionFairy being present
        # allows attribute set e.g. "connection.autocommit = True"
        # to work properly
        if hasattr(connection, "connection"):
            connection = connection.connection

        self._set_isolation_level(connection, level)

    def _set_isolation_level(self, connection, level):
        if level not in self._isolation_lookup:
            raise exc.ArgumentError(
                "Invalid value '%s' for isolation_level. "
                "Valid isolation levels for %s are %s"
                % (level, self.name, ", ".join(self._isolation_lookup))
            )
        cursor = connection.cursor()
        cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL %s" % level)
        cursor.execute("COMMIT")
        cursor.close()

    def get_isolation_level(self, connection):
        cursor = connection.cursor()
        if self._is_mysql and self.server_version_info >= (5, 7, 20):
            cursor.execute("SELECT @@transaction_isolation")
        else:
            cursor.execute("SELECT @@tx_isolation")
        val = cursor.fetchone()[0]
        cursor.close()
        if util.py3k and isinstance(val, bytes):
            val = val.decode()
        return val.upper().replace("-", " ")

    def _get_server_version_info(self, connection):
        # get database server version info explicitly over the wire
        # to avoid proxy servers like MaxScale getting in the
        # way with their own values, see #4205
        dbapi_con = connection.connection
        cursor = dbapi_con.cursor()
        cursor.execute("SELECT VERSION()")
        val = cursor.fetchone()[0]
        cursor.close()
        if util.py3k and isinstance(val, bytes):
            val = val.decode()

        return self._parse_server_version(val)

    def _parse_server_version(self, val):
        version = []
        r = re.compile(r"[.\-]")
        for n in r.split(val):
            try:
                version.append(int(n))
            except ValueError:
                mariadb = re.match(r"(.*)(MariaDB)(.*)", n)
                if mariadb:
                    version.extend(g for g in mariadb.groups() if g)
                else:
                    version.append(n)
        return tuple(version)

    def do_commit(self, dbapi_connection):
        """Execute a COMMIT."""

        # COMMIT/ROLLBACK were introduced in 3.23.15.
        # Yes, we have at least one user who has to talk to these old
        # versions!
        #
        # Ignore commit/rollback if support isn't present, otherwise even
        # basic operations via autocommit fail.
        try:
            dbapi_connection.commit()
        except Exception:
            if self.server_version_info < (3, 23, 15):
                args = sys.exc_info()[1].args
                if args and args[0] == 1064:
                    return
            raise

    def do_rollback(self, dbapi_connection):
        """Execute a ROLLBACK."""

        try:
            dbapi_connection.rollback()
        except Exception:
            if self.server_version_info < (3, 23, 15):
                args = sys.exc_info()[1].args
                if args and args[0] == 1064:
                    return
            raise

    def do_begin_twophase(self, connection, xid):
        connection.execute(sql.text("XA BEGIN :xid"), xid=xid)

    def do_prepare_twophase(self, connection, xid):
        connection.execute(sql.text("XA END :xid"), xid=xid)
        connection.execute(sql.text("XA PREPARE :xid"), xid=xid)

    def do_rollback_twophase(
        self, connection, xid, is_prepared=True, recover=False
    ):
        if not is_prepared:
            connection.execute(sql.text("XA END :xid"), xid=xid)
        connection.execute(sql.text("XA ROLLBACK :xid"), xid=xid)

    def do_commit_twophase(
        self, connection, xid, is_prepared=True, recover=False
    ):
        if not is_prepared:
            self.do_prepare_twophase(connection, xid)
        connection.execute(sql.text("XA COMMIT :xid"), xid=xid)

    def do_recover_twophase(self, connection):
        resultset = connection.execute("XA RECOVER")
        return [row["data"][0 : row["gtrid_length"]] for row in resultset]

    def is_disconnect(self, e, connection, cursor):
        if isinstance(
            e, (self.dbapi.OperationalError, self.dbapi.ProgrammingError)
        ):
            return self._extract_error_code(e) in (
                2006,
                2013,
                2014,
                2045,
                2055,
            )
        elif isinstance(
            e, (self.dbapi.InterfaceError, self.dbapi.InternalError)
        ):
            # if underlying connection is closed,
            # this is the error you get
            return "(0, '')" in str(e)
        else:
            return False

    def _compat_fetchall(self, rp, charset=None):
        """Proxy result rows to smooth over MySQL-Python driver
        inconsistencies."""

        return [_DecodingRowProxy(row, charset) for row in rp.fetchall()]

    def _compat_fetchone(self, rp, charset=None):
        """Proxy a result row to smooth over MySQL-Python driver
        inconsistencies."""

        row = rp.fetchone()
        if row:
            return _DecodingRowProxy(row, charset)
        else:
            return None

    def _compat_first(self, rp, charset=None):
        """Proxy a result row to smooth over MySQL-Python driver
        inconsistencies."""

        row = rp.first()
        if row:
            return _DecodingRowProxy(row, charset)
        else:
            return None

    def _extract_error_code(self, exception):
        raise NotImplementedError()

    def _get_default_schema_name(self, connection):
        return connection.execute("SELECT DATABASE()").scalar()

    def has_table(self, connection, table_name, schema=None):
        # SHOW TABLE STATUS LIKE and SHOW TABLES LIKE do not function properly
        # on macosx (and maybe win?) with multibyte table names.
        #
        # TODO: if this is not a problem on win, make the strategy swappable
        # based on platform.  DESCRIBE is slower.

        # [ticket:726]
        # full_name = self.identifier_preparer.format_table(table,
        #                                                   use_schema=True)

        full_name = ".".join(
            self.identifier_preparer._quote_free_identifiers(
                schema, table_name
            )
        )

        st = "DESCRIBE %s" % full_name
        rs = None
        try:
            try:
                rs = connection.execution_options(
                    skip_user_error_events=True
                ).execute(st)
                have = rs.fetchone() is not None
                rs.close()
                return have
            except exc.DBAPIError as e:
                if self._extract_error_code(e.orig) == 1146:
                    return False
                raise
        finally:
            if rs:
                rs.close()

    def initialize(self, connection):
        self._connection_charset = self._detect_charset(connection)
        self._detect_sql_mode(connection)
        self._detect_ansiquotes(connection)
        self._detect_casing(connection)
        if self._server_ansiquotes:
            # if ansiquotes == True, build a new IdentifierPreparer
            # with the new setting
            self.identifier_preparer = self.preparer(
                self, server_ansiquotes=self._server_ansiquotes
            )

        default.DefaultDialect.initialize(self, connection)

        self._needs_correct_for_88718 = (
            not self._is_mariadb and self.server_version_info >= (8,)
        )

        self._warn_for_known_db_issues()

    def _warn_for_known_db_issues(self):
        if self._is_mariadb:
            mdb_version = self._mariadb_normalized_version_info
            if mdb_version > (10, 2) and mdb_version < (10, 2, 9):
                util.warn(
                    "MariaDB %r before 10.2.9 has known issues regarding "
                    "CHECK constraints, which impact handling of NULL values "
                    "with SQLAlchemy's boolean datatype (MDEV-13596). An "
                    "additional issue prevents proper migrations of columns "
                    "with CHECK constraints (MDEV-11114).  Please upgrade to "
                    "MariaDB 10.2.9 or greater, or use the MariaDB 10.1 "
                    "series, to avoid these issues." % (mdb_version,)
                )

    @property
    def _is_mariadb(self):
        return (
            self.server_version_info and "MariaDB" in self.server_version_info
        )

    @property
    def _is_mysql(self):
        return not self._is_mariadb

    @property
    def _is_mariadb_102(self):
        return self._is_mariadb and self._mariadb_normalized_version_info > (
            10,
            2,
        )

    @property
    def _mariadb_normalized_version_info(self):
        # MariaDB's wire-protocol prepends the server_version with
        # the string "5.5"; now that we use @@version we no longer see this.

        if self._is_mariadb:
            idx = self.server_version_info.index("MariaDB")
            return self.server_version_info[idx - 3 : idx]
        else:
            return self.server_version_info

    @property
    def _supports_cast(self):
        return (
            self.server_version_info is None
            or self.server_version_info >= (4, 0, 2)
        )

    @reflection.cache
    def get_schema_names(self, connection, **kw):
        rp = connection.execute("SHOW schemas")
        return [r[0] for r in rp]

    @reflection.cache
    def get_table_names(self, connection, schema=None, **kw):
        """Return a Unicode SHOW TABLES from a given schema."""
        if schema is not None:
            current_schema = schema
        else:
            current_schema = self.default_schema_name

        charset = self._connection_charset
        if self.server_version_info < (5, 0, 2):
            rp = connection.execute(
                "SHOW TABLES FROM %s"
                % self.identifier_preparer.quote_identifier(current_schema)
            )
            return [
                row[0] for row in self._compat_fetchall(rp, charset=charset)
            ]
        else:
            rp = connection.execute(
                "SHOW FULL TABLES FROM %s"
                % self.identifier_preparer.quote_identifier(current_schema)
            )

            return [
                row[0]
                for row in self._compat_fetchall(rp, charset=charset)
                if row[1] == "BASE TABLE"
            ]

    @reflection.cache
    def get_view_names(self, connection, schema=None, **kw):
        if self.server_version_info < (5, 0, 2):
            raise NotImplementedError
        if schema is None:
            schema = self.default_schema_name
        if self.server_version_info < (5, 0, 2):
            return self.get_table_names(connection, schema)
        charset = self._connection_charset
        rp = connection.execute(
            "SHOW FULL TABLES FROM %s"
            % self.identifier_preparer.quote_identifier(schema)
        )
        return [
            row[0]
            for row in self._compat_fetchall(rp, charset=charset)
            if row[1] in ("VIEW", "SYSTEM VIEW")
        ]

    @reflection.cache
    def get_table_options(self, connection, table_name, schema=None, **kw):

        parsed_state = self._parsed_state_or_create(
            connection, table_name, schema, **kw
        )
        return parsed_state.table_options

    @reflection.cache
    def get_columns(self, connection, table_name, schema=None, **kw):
        parsed_state = self._parsed_state_or_create(
            connection, table_name, schema, **kw
        )
        return parsed_state.columns

    @reflection.cache
    def get_pk_constraint(self, connection, table_name, schema=None, **kw):
        parsed_state = self._parsed_state_or_create(
            connection, table_name, schema, **kw
        )
        for key in parsed_state.keys:
            if key["type"] == "PRIMARY":
                # There can be only one.
                cols = [s[0] for s in key["columns"]]
                return {"constrained_columns": cols, "name": None}
        return {"constrained_columns": [], "name": None}

    @reflection.cache
    def get_foreign_keys(self, connection, table_name, schema=None, **kw):

        parsed_state = self._parsed_state_or_create(
            connection, table_name, schema, **kw
        )
        default_schema = None

        fkeys = []

        for spec in parsed_state.fk_constraints:
            ref_name = spec["table"][-1]
            ref_schema = len(spec["table"]) > 1 and spec["table"][-2] or schema

            if not ref_schema:
                if default_schema is None:
                    default_schema = connection.dialect.default_schema_name
                if schema == default_schema:
                    ref_schema = schema

            loc_names = spec["local"]
            ref_names = spec["foreign"]

            con_kw = {}
            for opt in ("onupdate", "ondelete"):
                if spec.get(opt, False):
                    con_kw[opt] = spec[opt]

            fkey_d = {
                "name": spec["name"],
                "constrained_columns": loc_names,
                "referred_schema": ref_schema,
                "referred_table": ref_name,
                "referred_columns": ref_names,
                "options": con_kw,
            }
            fkeys.append(fkey_d)

        if self._needs_correct_for_88718:
            self._correct_for_mysql_bug_88718(fkeys, connection)

        return fkeys

    def _correct_for_mysql_bug_88718(self, fkeys, connection):
        # Foreign key is always in lower case (MySQL 8.0)
        # https://bugs.mysql.com/bug.php?id=88718
        # issue #4344 for SQLAlchemy

        # for lower_case_table_names=2, information_schema.columns
        # preserves the original table/schema casing, but SHOW CREATE
        # TABLE does not.   this problem is not in lower_case_table_names=1,
        # but use case-insensitive matching for these two modes in any case.

        if self._casing in (1, 2):

            def lower(s):
                return s.lower()

        else:
            # if on case sensitive, there can be two tables referenced
            # with the same name different casing, so we need to use
            # case-sensitive matching.
            def lower(s):
                return s

        default_schema_name = connection.dialect.default_schema_name
        col_tuples = [
            (
                lower(rec["referred_schema"] or default_schema_name),
                lower(rec["referred_table"]),
                col_name,
            )
            for rec in fkeys
            for col_name in rec["referred_columns"]
        ]

        if col_tuples:

            correct_for_wrong_fk_case = connection.execute(
                sql.text(
                    """
                    select table_schema, table_name, column_name
                    from information_schema.columns
                    where (table_schema, table_name, lower(column_name)) in
                    :table_data;
                """
                ).bindparams(sql.bindparam("table_data", expanding=True)),
                table_data=col_tuples,
            )

            # in casing=0, table name and schema name come back in their
            # exact case.
            # in casing=1, table name and schema name come back in lower
            # case.
            # in casing=2, table name and schema name come back from the
            # information_schema.columns view in the case
            # that was used in CREATE DATABASE and CREATE TABLE, but
            # SHOW CREATE TABLE converts them to *lower case*, therefore
            # not matching.  So for this case, case-insensitive lookup
            # is necessary
            d = defaultdict(dict)
            for schema, tname, cname in correct_for_wrong_fk_case:
                d[(lower(schema), lower(tname))][cname.lower()] = cname

            for fkey in fkeys:
                fkey["referred_columns"] = [
                    d[
                        (
                            lower(
                                fkey["referred_schema"] or default_schema_name
                            ),
                            lower(fkey["referred_table"]),
                        )
                    ][col.lower()]
                    for col in fkey["referred_columns"]
                ]

    @reflection.cache
    def get_check_constraints(self, connection, table_name, schema=None, **kw):
        parsed_state = self._parsed_state_or_create(
            connection, table_name, schema, **kw
        )

        return [
            {"name": spec["name"], "sqltext": spec["sqltext"]}
            for spec in parsed_state.ck_constraints
        ]

    @reflection.cache
    def get_table_comment(self, connection, table_name, schema=None, **kw):
        parsed_state = self._parsed_state_or_create(
            connection, table_name, schema, **kw
        )
        return {"text": parsed_state.table_options.get("mysql_comment", None)}

    @reflection.cache
    def get_indexes(self, connection, table_name, schema=None, **kw):

        parsed_state = self._parsed_state_or_create(
            connection, table_name, schema, **kw
        )

        indexes = []

        for spec in parsed_state.keys:
            dialect_options = {}
            unique = False
            flavor = spec["type"]
            if flavor == "PRIMARY":
                continue
            if flavor == "UNIQUE":
                unique = True
            elif flavor in ("FULLTEXT", "SPATIAL"):
                dialect_options["mysql_prefix"] = flavor
            elif flavor is None:
                pass
            else:
                self.logger.info(
                    "Converting unknown KEY type %s to a plain KEY", flavor
                )
                pass

            if spec["parser"]:
                dialect_options["mysql_with_parser"] = spec["parser"]

            index_d = {}
            if dialect_options:
                index_d["dialect_options"] = dialect_options

            index_d["name"] = spec["name"]
            index_d["column_names"] = [s[0] for s in spec["columns"]]
            index_d["unique"] = unique
            if flavor:
                index_d["type"] = flavor
            indexes.append(index_d)
        return indexes

    @reflection.cache
    def get_unique_constraints(
        self, connection, table_name, schema=None, **kw
    ):
        parsed_state = self._parsed_state_or_create(
            connection, table_name, schema, **kw
        )

        return [
            {
                "name": key["name"],
                "column_names": [col[0] for col in key["columns"]],
                "duplicates_index": key["name"],
            }
            for key in parsed_state.keys
            if key["type"] == "UNIQUE"
        ]

    @reflection.cache
    def get_view_definition(self, connection, view_name, schema=None, **kw):

        charset = self._connection_charset
        full_name = ".".join(
            self.identifier_preparer._quote_free_identifiers(schema, view_name)
        )
        sql = self._show_create_table(
            connection, None, charset, full_name=full_name
        )
        return sql

    def _parsed_state_or_create(
        self, connection, table_name, schema=None, **kw
    ):
        return self._setup_parser(
            connection,
            table_name,
            schema,
            info_cache=kw.get("info_cache", None),
        )

    @util.memoized_property
    def _tabledef_parser(self):
        """return the MySQLTableDefinitionParser, generate if needed.

        The deferred creation ensures that the dialect has
        retrieved server version information first.

        """
        if self.server_version_info < (4, 1) and self._server_ansiquotes:
            # ANSI_QUOTES doesn't affect SHOW CREATE TABLE on < 4.1
            preparer = self.preparer(self, server_ansiquotes=False)
        else:
            preparer = self.identifier_preparer
        return _reflection.MySQLTableDefinitionParser(self, preparer)

    @reflection.cache
    def _setup_parser(self, connection, table_name, schema=None, **kw):
        charset = self._connection_charset
        parser = self._tabledef_parser
        full_name = ".".join(
            self.identifier_preparer._quote_free_identifiers(
                schema, table_name
            )
        )
        sql = self._show_create_table(
            connection, None, charset, full_name=full_name
        )
        if re.match(r"^CREATE (?:ALGORITHM)?.* VIEW", sql):
            # Adapt views to something table-like.
            columns = self._describe_table(
                connection, None, charset, full_name=full_name
            )
            sql = parser._describe_to_create(table_name, columns)
        return parser.parse(sql, charset)

    def _detect_charset(self, connection):
        raise NotImplementedError()

    def _detect_casing(self, connection):
        """Sniff out identifier case sensitivity.

        Cached per-connection. This value can not change without a server
        restart.

        """
        # http://dev.mysql.com/doc/refman/5.0/en/name-case-sensitivity.html

        charset = self._connection_charset
        row = self._compat_first(
            connection.execute("SHOW VARIABLES LIKE 'lower_case_table_names'"),
            charset=charset,
        )
        if not row:
            cs = 0
        else:
            # 4.0.15 returns OFF or ON according to [ticket:489]
            # 3.23 doesn't, 4.0.27 doesn't..
            if row[1] == "OFF":
                cs = 0
            elif row[1] == "ON":
                cs = 1
            else:
                cs = int(row[1])
        self._casing = cs
        return cs

    def _detect_collations(self, connection):
        """Pull the active COLLATIONS list from the server.

        Cached per-connection.
        """

        collations = {}
        if self.server_version_info < (4, 1, 0):
            pass
        else:
            charset = self._connection_charset
            rs = connection.execute("SHOW COLLATION")
            for row in self._compat_fetchall(rs, charset):
                collations[row[0]] = row[1]
        return collations

    def _detect_sql_mode(self, connection):
        row = self._compat_first(
            connection.execute("SHOW VARIABLES LIKE 'sql_mode'"),
            charset=self._connection_charset,
        )

        if not row:
            util.warn(
                "Could not retrieve SQL_MODE; please ensure the "
                "MySQL user has permissions to SHOW VARIABLES"
            )
            self._sql_mode = ""
        else:
            self._sql_mode = row[1] or ""

    def _detect_ansiquotes(self, connection):
        """Detect and adjust for the ANSI_QUOTES sql mode."""

        mode = self._sql_mode
        if not mode:
            mode = ""
        elif mode.isdigit():
            mode_no = int(mode)
            mode = (mode_no | 4 == mode_no) and "ANSI_QUOTES" or ""

        self._server_ansiquotes = "ANSI_QUOTES" in mode

        # as of MySQL 5.0.1
        self._backslash_escapes = "NO_BACKSLASH_ESCAPES" not in mode

    def _show_create_table(
        self, connection, table, charset=None, full_name=None
    ):
        """Run SHOW CREATE TABLE for a ``Table``."""

        if full_name is None:
            full_name = self.identifier_preparer.format_table(table)
        st = "SHOW CREATE TABLE %s" % full_name

        rp = None
        try:
            rp = connection.execution_options(
                skip_user_error_events=True
            ).execute(st)
        except exc.DBAPIError as e:
            if self._extract_error_code(e.orig) == 1146:
                raise exc.NoSuchTableError(full_name)
            else:
                raise
        row = self._compat_first(rp, charset=charset)
        if not row:
            raise exc.NoSuchTableError(full_name)
        return row[1].strip()

        return sql

    def _describe_table(self, connection, table, charset=None, full_name=None):
        """Run DESCRIBE for a ``Table`` and return processed rows."""

        if full_name is None:
            full_name = self.identifier_preparer.format_table(table)
        st = "DESCRIBE %s" % full_name

        rp, rows = None, None
        try:
            try:
                rp = connection.execution_options(
                    skip_user_error_events=True
                ).execute(st)
            except exc.DBAPIError as e:
                code = self._extract_error_code(e.orig)
                if code == 1146:
                    raise exc.NoSuchTableError(full_name)
                elif code == 1356:
                    raise exc.UnreflectableTableError(
                        "Table or view named %s could not be "
                        "reflected: %s" % (full_name, e)
                    )
                else:
                    raise
            rows = self._compat_fetchall(rp, charset=charset)
        finally:
            if rp:
                rp.close()
        return rows


class _DecodingRowProxy(object):
    """Return unicode-decoded values based on type inspection.

    Smooth over data type issues (esp. with alpha driver versions) and
    normalize strings as Unicode regardless of user-configured driver
    encoding settings.

    """

    # Some MySQL-python versions can return some columns as
    # sets.Set(['value']) (seriously) but thankfully that doesn't
    # seem to come up in DDL queries.

    _encoding_compat = {
        "koi8r": "koi8_r",
        "koi8u": "koi8_u",
        "utf16": "utf-16-be",  # MySQL's uft16 is always bigendian
        "utf8mb4": "utf8",  # real utf8
        "eucjpms": "ujis",
    }

    def __init__(self, rowproxy, charset):
        self.rowproxy = rowproxy
        self.charset = self._encoding_compat.get(charset, charset)

    def __getitem__(self, index):
        item = self.rowproxy[index]
        if isinstance(item, _array):
            item = item.tostring()

        if self.charset and isinstance(item, util.binary_type):
            return item.decode(self.charset)
        else:
            return item

    def __getattr__(self, attr):
        item = getattr(self.rowproxy, attr)
        if isinstance(item, _array):
            item = item.tostring()
        if self.charset and isinstance(item, util.binary_type):
            return item.decode(self.charset)
        else:
            return item
