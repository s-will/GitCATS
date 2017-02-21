[![Build Status](https://travis-ci.org/s-will/GitCATS.svg?branch=master)](https://travis-ci.org/s-will/GitCATS)

# GitCATS --- Git-based Class Assignment Testing System

Copyright Sebastian Will, 2017

Provides travis configuration and a python script to supports
automatic testing of class assignments (for offline use or CI
testing.)

The typical usage scenario of this script is for running the
submission and reviewing process of programming assignments via github
in one central repository for a small number of students, where the
teachers can still look at all submissions, but want to partially
automatize test runs and reviewing. The entire process is public such
that all students can see the submissions of others; intentionally, no
attempts for privacy are made.

Main features:

 * configurable via yml files
     assignments.yml  languages.yml  participants.yml  submissions.yml
   Commented examples are provided.

 * ready to be loaded as submodule into git repository

 * multiple users/"participants", multiple languages

 * potential language-specific dependencies are installed on demand via conda 

 * multiple assignments, multiple tests per assignments

 * default testing by diff to expected output


----------------------------------------
Installing and using this framework
----------------------------------------

* In a new class repository (put on github), add this repository as submodule:

  git submodule add git@github.com:s-will/GitCATS.git

  and commit this like

  git commit -am "Add submodule GitCATS"

* Link .travis from the GitCATS directory into the root directory of your repository

* Copy all example yaml configuration files from GitCATS to the root
  directory and edit them for your purposes

