# lr-visa
## About
This is a early stage set of tools that came out of about three days across a
few different months of hacking with various measurement tools. Initially this
was done via the python usbtmc interface, but eventually most of it was moved
to the pyvisa library to enable networking support.

## General Usage
Most of the classes are designed to be imported and then initialized to a handle
for the various pieces of hardware you want to work with. If you want to use
multiple hardware components, currently you should pass existing VISA resource
managers rather than calling the new instances empty.

To protect you from activating hardware right out of the gate, you must pass the
`DRY` argument in the constructor methods to enable the hardware. If you don't
the software will attempt to operate in a *"dry run"* configuration where no
actions are taken, but the command line is filled with verbose messages about
the commands that would be sent to the hardware.


```python
from pnaPNAX import pnaPNAX
from psuN6705B import psuN6705B, PSU_Sample
h_pna = pnaPNAX(DRY=False) # generate the first object
h_psu = psuN6705B(rm=h_pna.rm, DRY=False) # copy the existing resource manager
```

## Old Junk
The *old_references* path contains some preliminary tinkering code I used to
run my tests in all of it's hideous glory.

## License?
To be determined "soon".

## Disclaimer
The code is very ugly, and really *needs* to be refactored. There is so much
duplicated code it's actually kind of embarrassing. Furthermore, I am aware that
there are some other projects that are trying to generalize a bit of this stuff,
but I haven't had a chance to dig into mapping the hardware at my disposal to
these libraries.
