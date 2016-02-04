# Yet another MGC compiler
Compiler project for Formal Languages &amp; Translation Techniques 2015 classes.

Author: Adam Bobowski


Requirenments:
- python 2.7.x         (tested on 2.7.6)
- PLY (python package)   (tested on 3.8)


Instalation:
Get Python-Lex-Yacc (PLY) from pip

```
$ sudo apt-get install python-pip
$ sudo pip install ply
```

Compilation with Yamc:
```
$ python yamc.py [file] [--out OUT]
```
if OUT ommited returns a.mr

If chmod +x can be run as script:
```
$ yamc.py [file] [--out OUT]
```
