# Recmd: Inspired by zx command constructor

Easy to use, type-safe (pyright), sync and async, and cross-platform command executor

## Installation

Install recmd using pip: `pip install recmd`
With async support: `pip install recmd[async]`

## Usage

#### Convert formatted strings to argument lists


Using ast transformation (python 3.12+):
```py
from recmd import shell, sh

@sh
def argument_list(value: str, *args):
    return shell(f"executable arguments --value {value} 'more arguments with {value}' {args:*!s}")
    # :*!s converts args into `*[f"{x!s}" for x in args]`
    # if !s is omitted then it turned into just `*args`
    # you can also add any python format after :* (:*:.2f)

assert argument_list("test asd", 1, 2, 3) == [
    "executable", "arguments", "--value", "test asd", "more arguments with test asd", "1", "2", "3"
]
```

Using template strings (python 3.14+):
```py
from recmd import shell

def argument_list(value: str, *args):
    return shell(t"executable arguments --value {value} 'more arguments with {value}' {args:*!s}")
    # :*!s converts args into `*[f"{x!s}" for x in args]`
    # if !s is omitted then it turned into just `*args`
    # you can also add any python format after :* (:*:.2f)

assert argument_list("test asd", 1, 2, 3) == [
    "executable", "arguments", "--value", "test asd", "more arguments with test asd", "1", "2", "3"
]
```
#### Constructing commands

Using ast transformation (python 3.12+):
```py
import sys
from recmd.shell import sh

@sh
def python(code: str, *args):
    return sh(f"{sys.executable} -c {code} {args:*}")

```

Using template strings (python 3.14+):
```py
import sys
from recmd.shell import sh

def python(code: str, *args):
    return sh(t"{sys.executable} -c {code} {args:*}")

```

#### Running commands

Sync:

```py
from recmd.executor.subprocess import SubprocessExecutor

# set globally (context api)
SubprocessExecutor.context.set(SubprocessExecutor())

# set for code block
with SubprocessExecutor().use():
    ...


# `~` runs and waits for process to exit, then `assert` checks that exit code == 0
assert ~python("pass")

# you can also use process as context manager
with python("pass"):
    pass

```

Async:

```py
import anyio
from recmd.executor.anyio import AnyioExecutor

# set globally (context api)
AnyioExecutor.context.set(AnyioExecutor())

# set for code block
with AnyioExecutor().use():
    ...

async def run():
    # `await` runs and waits for process to exit, then `assert` checks that exit code == 0
    assert await python("pass")

    # you can also use process as context manager
    async with python("pass"):
        pass

anyio.run(run)
```

#### Interacting with processes

Sync:

```py
# send to stdin and read from stdout
assert ~python("print(input(),end='')").send("123").output() == "123"

from recmd import IOStream


# manually control streams
with IOStream() >> python("print(input(),end='')") >> IOStream() as process:
    process.stdin.sync_io.write(b"hello")
    process.stdin.sync_io.close()
    assert process.stdout.sync_io.read() == b"hello"
```

Async:

```py
# send to stdin and read from stdout
assert await python("print(input(),end='')").send("123").output() == "123"

from recmd import IOStream


# manually control streams
async with IOStream() >> python("print(input(),end='')") >> IOStream() as process:
    await process.stdin.async_write.send(b"hello")
    await process.stdin.async_write.aclose()
    assert await process.stdout.async_read.receive() == "bhello"
```

#### Pipes

Sync:

```py
# redirect stdout from first process to stdin of second
from recmd import Capture

group = ~(python("print(123)") | python("print(input(),end='')") >> Capture())

with python("print(123)") | python("print(input(),end='')") >> Capture() as group:
    ...

assert group.commands[-1].stdout.get() == b"123"
```

Async:

```py
# redirect stdout from first process to stdin of second
from recmd import Capture

group = await (python("print(123)") | python("print(input(),end='')") >> Capture())

async with python("print(123)") | python("print(input(),end='')") >> Capture() as group:
    ...

assert group.commands[-1].stdout.get() == b"123"
```
