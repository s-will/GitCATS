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


----------------------------------------
Main features:
----------------------------------------

 * configurable via yml files
     assignments.yml  languages.yml  participants.yml  submissions.yml
   Commented examples are provided.

 * ready to be loaded as subtree into git repository

 * multiple users/"participants", multiple languages

 * potential language-specific dependencies are installed on demand via conda 

 * multiple assignments, multiple tests per assignments

 * multiple submissions per assignment per participant

 * default testing by diff to expected output


----------------------------------------
Installing the framework
----------------------------------------

* In the class repository, add this repository as subtree
```
    git remote add gitcats git@github.com:s-will/GitCATS.git
    git subtree add --prefix GitCATS --squash gitcats master
```
* Link .travis from the GitCATS directory into the root directory of your repository
```
    ln -s GitCATS/.travis.yml .
```
* Copy all example yaml configuration files from GitCATS to the root
  directory; remove the 'DO NOT EDIT' warning; and then edit them for
  your purposes
```
    cp GitCATS/*.yml .
    sed -i '/^#%.*/ d' assignments.yml  languages.yml  participants.yml  submissions.yml
```
* on Github register the repository for Travis CI


----------------------------------------
Using the framework
----------------------------------------

* register participants in participants.yml (better, let them register)

* edit assignments.yml to define new assignments and tests

  make assignment directories
  place test input and output in the assignment directories
  
* if necessary, define new languages in languages.yml (and possibly contribute to the project)

* let students clone the repo and create their participants branches 
  (those branches are named by their registered short-name, usually the github name)

* let students solve the assignemnts, submit, and register there submissions in submissions.yml

* let students make pull requests for their participant branches into the master

* discuss PRs via github; after acceptance, let students set checked to true (to avoid further tests) and merge into master
