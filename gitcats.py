#!/usr/bin/env python

"""This script is part of

GitCATS --- Git-based Class Assignment Testing System

The script supports automatic testing of class assignments (for
offline use or CI testing.)

Main features:

 * configurable via yml files

 * multiple users/"participants", multiple languages

 * potential language-specific dependencies are installed on demand
   via conda

 * multiple assignments, multiple tests per assignments

 * default testing by diff to expected output

 * support multiple submissions per assignment per user

    - allows /lists of submissions/ in
      submissions.$assignment_name.$partiticipant_name

    - consequently, submission filenames change to
      ${partiticipant_name}-${submission_index}-${assignment_name}.$suffix
      where ${submission_index} is a the index 0,... in the list of
      submissions

Copyright Sebastian Will, 2017


IDEAS for extensions:

 * support more flexible installation of dependencies

    - idea: support apt installation of required dependencies (besides conda)

        - issues: apt requires sudo, but this limits Travis; moreover
          gitcats.py should not run with sudo rights (which requires
          separate installation)
        - btw, can one generate the travis script on-the-fly?

 * support different tests (of the same program run; when it does not fail)

    - motivation: testing for 'almost' correct output could help to to
      identify still existing problems (correctness up to whitespace
      errors, order of solutions, non-canonical representation,
      redundancy of solutions...)

    - allow list of checks in the test record of the assignment,
      i.e. in assignments[i].tests[j].check for each check, support
      entries 'description' and 'command'.  Tests are hierarchical,
      i.e. test until one of the test fails or all tests are passed;
      print test description followed by 'OK' or 'FAIL' (unless all
      tests succeed.)

  This could look like

assignments:
  - name: Administration
    directory: A2
    tests:
      - name: test1
        check:
          - description: "Are all solutions generated?"
            command: ...
          - description: "Are exactly the expected solutions generated, but not necessarily unique?"
            command: ...
          - description: "Are exactly the expected solutions generated, but possibly in the wrong order?"
            command: ...
          - description: "Is the exactly the expected output generated, allowing whitespace errors?" 
            ...
          - description: "Is the exactly the expected output generated?" 
            ...

"""

import yaml
import argparse
import logging
import os
import subprocess
import re

def load_test_configuration():
    """Load the configuration from the yaml files"""

    configuration = dict()
    for config in ["assignments",
                   "participants",
                   "languages",
                   "submissions"]:
        try:
            fh = open(config+".yml");
            c = yaml.load(fh);
            if config in c:
                configuration[config] = c[config]
            else:
                logging.error("Configuration file "+config+".yml needs entry "+config+"!");
                return None

        except IOError:
            logging.error("Cannot read configuration file "+config+".yml!")
            return None
        except yaml.YAMLError as exc:
            logging.error("Cannot parse configuration file "+config+".yml!");
            if hasattr(exc, 'problem_mark'):
                mark = exc.problem_mark
                logging.error("    Syntax error at line {}, column {}".format(mark.line+1, mark.column+1))
            return None
    return configuration

def exists_and_equals(k,h,val):
    """Test whether key k exists in hash h and has value val.
    """
    return (k in h) and (h[k]==val)

def exists_and_defined(k,h):
    """Test whether key k exists in hash h and is not None.
    """
    return (k in h) and h[k] is not None

def is_executable(fpath):
    return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

def make_program_name(participant_name, submission_name, submission_index):
    if submission_index==0:
        return "-".join([participant_name,submission_name])
    else:
        return "-".join([participant_name,str(submission_index),submission_name])

def get_feature(d,key,default):
    """
    Get feature if exists and is not None else default
    @param d dictionary
    @param key name of the feature
    @param default default value
    @return feature value if key exists is not None or default value otherwise
    """
    return d[key] if exists_and_defined(key,d) else default

def derive_conda_env_name(language):
    """
    Derive a conda environment name for the language
    """
    
    return ("__gitcats-" +
            re.sub('\W+','_',
            get_feature(language,"conda-install","")))

def get_submission_language(submission):
    return get_feature(submission,"language","default")

def lookup_assignment(assignment_name,configuration):
    assignments=configuration["assignments"]
    for a in assignments: 
        if a["name"]==assignment_name: 
            return a
    return  None

def enumerate_tests(participant_name, assignment, submission_index, the_tests):
    """
    Enumerate the tests that must be performed for an assignment
    @param participant_name name of the participant
    @param assignment the assignment record
    @param[out] the_tests list of the tests
    """
    assignment_name = assignment["name"]
    
    tests=list()
    if "tests" in assignment:
        tests=assignment["tests"]
    else:
        logging.warn("The assignment "+assignment_name+" does not specify any tests.");
        return

    for test_id,test in enumerate(tests):
        the_tests.append([participant_name,assignment,submission_index,test_id,test])

def create_conda_env(submission, the_conda_environments, configuration):
    """
    Create the conda environment for the test, unless it exists already.
    Register the environment.
    
    @return success status
    """
    
    language_name = get_submission_language(submission)

    language = configuration["languages"][language_name]
    
    if exists_and_defined("conda-install", language):
        conda_env_name = derive_conda_env_name(language)
        
        if conda_env_name in the_conda_environments:
            return True

        the_conda_environments[conda_env_name]=True

        logging.debug("Setup conda environment for "+language_name+" in "+conda_env_name)

        conda_create_command="conda create"
        if not logging.getLogger().isEnabledFor(logging.DEBUG):
            conda_create_command += " >/dev/null"
        conda_create_command += " -y -n "+conda_env_name+" "+language["conda-install"]

        try:
            subprocess.check_call(conda_create_command, shell=True)
        except subprocess.CalledProcessError as exc:
            logging.error("Failure to create conda environment.")
            logging.debug(exc)
            return False
    return True

def cleanup_conda_env(conda_env_name):
    """cleanup conda environment"""
    logging.debug("Cleanup conda environment "+conda_env_name)
    subprocess.call("conda env remove >/dev/null -y -n "+conda_env_name, shell=True)

def compile_submission(participant_name,
                       submission_name,
                       submission_index,
                       the_conda_environments,
                       configuration):
    """
    Run the compilation for a submission
    @param submission the submission dictionary (of a participant)
    @param configuration the configuration
    @return success status
    """
    
    logging.debug("Compile submission "+submission_name
                  +" "+str(submission_index)
                  +" of "+participant_name)

    submission=configuration["submissions"][submission_name][participant_name][submission_index]
    assignment=lookup_assignment(submission_name,configuration)

    language_name = get_submission_language(submission)
    language = configuration["languages"][language_name]

    directory=assignment["directory"]
    
    if "compile" in language:
        prog_name = make_program_name(participant_name, submission_name, submission_index)
        compile_command = language["compile"].format(
            name=prog_name,
            suffix=language["suffix"]
        )

        conda_env_name = derive_conda_env_name(language)

        shell_script = list()

        shell_script.append( "cd "+directory )
        if conda_env_name in the_conda_environments:
            shell_script.append( "source activate "+conda_env_name )

        shell_script.append(compile_command)

        if conda_env_name in the_conda_environments:
            shell_script.append( "source deactivate "+conda_env_name )

        shell_script = ("bash -s <<EOF\n"
                        + "\n".join(shell_script)
                        + "\nEOF")

        try:
            logging.debug("Execute shell script to compile "+prog_name+":\n"+shell_script)
            subprocess.check_call(shell_script,shell=True)
        
        except subprocess.CalledProcessError as exc:
            logging.warning("Exception subprocess.CalledProcessError raised while running test.")
            logging.debug(exc)
            return False
        
        except FileNotFoundError as exc:
            logging.warning("Exception FileNotFoundError raised while running test.")
            logging.debug(exc)
            return False

    return True

def run_test(test_spec,test_results,the_conda_environments,configuration):
    """
    Run tests for an assignment
    @param test_spec = [participant_name, assignment, submission_index, test_id, test]
    @subparam participant_name name of the participant
    @subparam assignment the assignment record
    @subparam test_id index of the test
    @subparam test dictionary of the test
    @param test_results hash of the test results
    @param configuration the entire configuration

    @todo merge with run_test
    """

    [participant_name, assignment, submission_index, test_id, test] = test_spec

    assignment_name = assignment["name"]
    
    status="OK" # be optimistic;)
    fail_status = "failed" if get_feature(test,"optional",False) else "FAILED" 
   
    timeout=get_feature(test,"timeout",None)

    assignment_name = assignment["name"]
    submission = configuration["submissions"][assignment_name][participant_name][submission_index]

    test_descr=str(test_id+1)
    if not "name" in test:
        logging.warn("Missing name in test "+test_descr+" of assignment '"+assignment_name+"'.")
    else:
        test_descr = test["name"]
    test_descr = test_descr

    directory = assignment["directory"]
        
    program_name = make_program_name(participant_name, assignment_name, submission_index)
    
    ## check language of submission
    language_name=submission["language"] if "language" in submission else "default"
    
    language=configuration["languages"][language_name]
    
    suffix = language["suffix"] if "suffix" in language else ""
    
    logging.info("Run test '{}' for program '{}{}' ...".format(test_descr,
                                                               os.path.join(directory,program_name),
                                                               suffix))
    testcall_params={'name': program_name,
                     'suffix': suffix,
                     'infile': assignment_name+"-"+test_descr+".in",
                     'outfile': assignment_name+"-"+test_descr+".out", # expected output file
                     'genfile': assignment_name+"-"+test_descr+".gen", # generated output file
                     'arguments': get_feature(test,"arguments","")}

    program_call = os.path.join(".",program_name)
    if "call" in language:
        program_call = language["call"].format(**testcall_params)

    conda_env_name=None
    
    try:
        shell_script=list()

        ## setup language environment
        
        if exists_and_defined("conda-install", language):
            conda_env_name = derive_conda_env_name(language)
            if conda_env_name in the_conda_environments:
                shell_script.append("source activate "+conda_env_name)

        shell_script.append("cd "+directory)
        shell_script.append("set -o pipefail")
        
        if timeout is not None:
            timeout_call = "timeout " + timeout + " "
        else:
            timeout_call = ""

        program_call_command = ("time "
                                +timeout_call
                                +program_call
                                +" {arguments} {infile} > {genfile}".format(**testcall_params))

        check_command = "diff -d -y --suppress-common-lines {genfile} {outfile} | head -n10".format(**testcall_params)
        if exists_and_defined("check", test):
            check_command = test["check"].format(**testcall_params)

        logging.info("Program call: "+program_call_command)
        logging.info("Check by:     "+check_command)
        if timeout is not None:
            logging.info("Timeout: "+timeout)

        prog_call_script = list(shell_script)
        prog_call_script.append(program_call_command)
        prog_call_script = ("bash -s <<EOF\n"
                        + "\n".join(prog_call_script)
                        + "\nEOF")
        logging.debug("Execute shell script\n"+prog_call_script)
        subprocess.check_call(prog_call_script, shell=True)
        
        test_call_script = list(shell_script)
        test_call_script.append(check_command)
        test_call_script = ("bash -s <<EOF\n"
                        + "\n".join(test_call_script)
                        + "\nEOF")
        logging.debug("Execute shell script\n"+test_call_script)

        subprocess.check_call(test_call_script, shell=True)
        
    except subprocess.CalledProcessError as exc:
        if exc.returncode==124:
            logging.debug("Test call timed out.")
            status = fail_status+" (time out)"
        else:
            logging.debug("Test call failed or does not produce expected result.")
            logging.debug(exc)
            status = fail_status
        
    except FileNotFoundError as exc:
        logging.warning("Test call failed (file not found).")
        logging.debug(exc)
        status = fail_status
    
    if status=="FAILED":
        logging.error(" ... "+status+".")
    else:
        logging.info(" ... "+status+".")

    test_results.append({
        "participant_name": participant_name,
        "assignment_name": assignment_name,
        "submission_index": submission_index,
        "test_description": test_descr,
        "status": status
    })

def syntax_checks(configuration):
    """
    Perform some general syntax checks of the configuration
    (required features)
    """
    for assignment_index,assignment in enumerate(configuration["assignments"]):
        for feature in ["name","directory"]:
            if not feature in assignment:
                logging.error("Missing required feature "+feature+" in assignment "+str(assignment_index+1)+"!")
                exit(-1);

def check_submission(participant_name, submission_name, submission_index, configuration):
    """
    Check submission configuration
    
    checks whether program exists, correct language specified etc...
    @return whether submission is valid for testing
    """
    submission = configuration["submissions"][submission_name][participant_name][submission_index]

    logging.debug("Check validity of submission "+str(submission_name)
                  +" "+str(submission_index)
                  +" of "+participant_name
                  +": "+str(submission))
        
    if submission is None:
        return False

    for assignment in configuration["assignments"]:
        languages=configuration["languages"]
        
        if assignment["name"] == submission_name:
            if exists_and_defined("language", submission):
                if not submission["language"] in languages:
                    logging.warning("Submission "+submission_name+" defines language "+submission["language"]
                                    +", which is not defined!")
                    return False
            else:
                submission["language"]="default"
            
            language  = submission["language"]
            suffix    = languages[language]["suffix"]
            directory = assignment["directory"]
            
            program_name = os.path.join(directory,
                                        make_program_name(participant_name,
                                                          submission_name,
                                                          submission_index))
            program_name = program_name+suffix
                
            if not os.path.isfile(program_name):
                logging.warn("Submission "+assignment["name"]+" of "+participant_name
                                 +" requires file "+program_name+" (language: "+language+").")
                return False

            if submission["language"] == "default":
                if not is_executable(program_name):
                    logging.warn("Submission "+assignment["name"]+" of "+participant_name
                                 +" requires "+program_name+" to be executable (language: "+language+").")
                    return False
    
            return True
    logging.warn("Submission name "+submission_name+" is not defined as assignment name.")
    return False

def main( args ):
    participant_name=args.participant

    ## load configuration; exit on error
    configuration = load_test_configuration();
    if configuration is None:
        exit(-1)
    
    # show complete configuration (debugging)
    logging.debug(configuration)

    syntax_checks(configuration)
    
    # is the participant known?
    if participant_name in configuration["participants"]:
        logging.info("Perform tests for participant "+participant_name)
    else:
        logging.info(participant_name+" is not known as the account name of a participant.\n"
        +"For pull requests, tests are performed only if the\n"
        +"name of the source branch is the name of a registered participant.")
        logging.info("No tests are performed.")
        exit(0)


    failed_submissions=list()

    # determine un-tested submissions
    test_assignments=list()
    for submission_name in configuration["submissions"]:
        submission = configuration["submissions"][submission_name]
        if submission is not None and participant_name in submission:
            if not isinstance(submission[participant_name],list):
                submission[participant_name] = [ submission[participant_name] ]

            for submission_index in range(0,len(submission[participant_name])):
                # check general validity of participant's submissions
                if check_submission(participant_name, submission_name, submission_index, configuration):
                    # check whether submission needs testing
                    if not exists_and_equals("checked",
                                             submission[participant_name][submission_index],
                                             True):
                        test_assignments.append((submission_name, submission_index))
                else:
                    failed_submissions.append([submission_name, submission_index, "INVALID"])

    if len(test_assignments)>0:
        logging.info("Perform tests for submissions "+str(test_assignments))
    
    test_results=list()

    the_conda_environments=dict()

    # for the un-tested submissions, 
    #   setup conda environments 
    #   and compile if necessary
    for (submission_name, submission_index) in test_assignments:
        submission=configuration["submissions"][submission_name][participant_name][submission_index]
        assignment=lookup_assignment(submission_name,configuration)
        if (not args.skip_depends and 
            not create_conda_env(submission, the_conda_environments, configuration)):
            test_assignments.remove((submission_name, submission_index))
            failed_submissions.append([submission_name,"DEPENDENCY_FAILED"])
        elif not compile_submission(participant_name, submission_name, submission_index,
                                    the_conda_environments, configuration):
            test_assignments.remove((submission_name, submission_index))
            failed_submissions.append((submission_name,
                                       submission_index,
                                       "COMPILE_FAILED"))          


    ## determine the tests that we want to perform
    the_tests = list()
    for assignment in configuration["assignments"]:
        for (test_assignment, submission_index) in test_assignments:
            if assignment["name"] == test_assignment:
                enumerate_tests(participant_name, assignment, submission_index, the_tests)
    

    # perform tests for the (valid) un-tested submissions
    logging.debug("Perform the tests")
    for test_spec in the_tests:
        run_test(test_spec, test_results, the_conda_environments, configuration)
        
    # cleanup all created conda environments
    for env in the_conda_environments:
        cleanup_conda_env(env)
    the_conda_environments=dict()

    # ========================================
    # Final assessment
    #
    
    summary_table=list()
    summary_table.append("")
    summary_table.append("==========================================================")
    summary_table.append("======================== SUMMARY =========================")
    summary_table.append("")
    
    exit_val=0
    all_ok=True
    
    row_format_string="{participant_name:16} {assignment_name:16} {submission_index:2} {test_description:16} {status:6}"

    if len(test_results)>0 or len(failed_submissions)>0:
        summary_table.append(row_format_string.format(
            participant_name="PARTICIPANT",
            assignment_name="ASSIGNMENT",
            submission_index="ID",
            test_description="TEST",
            status="STATUS"
        ))
        summary_table.append("----------------------------------------------------------")
    
    for entry in test_results:
        summary_table.append(row_format_string.format(**entry))
        if entry["status"][0:6] == "FAILED":
            all_ok = False
            
    for (submission_name, submission_index, fail_status) in failed_submissions:
        summary_table.append(row_format_string.format(
            participant_name=participant_name,
            assignment_name=submission_name,
            submission_index=submission_index,
            test_description="*",
            status=fail_status
        ))
        

    if len(test_results)>0 or len(failed_submissions)>0:
        summary_table.append("")
    
    logging.info("\n    ".join(summary_table))

    if all_ok:
        if len(test_results)>0:
            if len(failed_submissions) == 0:
                logging.info("All required tests passed. CONGRATULATIONS!")
            else:
                logging.info("At least the valid tests passed :-)")
        else:
            logging.info("No tests performed.")
    else:
        logging.warning("Some tests FAILED.")
        exit_val=-1

    if len(failed_submissions) > 0:
        logging.error("There were FAILED submissions, which have to be corrected.")
        exit_val=-1
 
    if exit_val == 0:
        logging.info("You're all set! :-)")
    else:
        logging.error("There is STILL WORK TO DO!")

    exit(exit_val)

if __name__=="__main__":
    parser = argparse.ArgumentParser("Run assignment tests of a participant")
    parser.add_argument('--participant', help="Registered name of participant.")
    parser.add_argument('--skip-depends', action="store_true",
                        help="Skip installation of language dependencies.")
    parser.add_argument('--loglevel', default="INFO", help="Logging level")

    args = parser.parse_args()

    numeric_loglevel = getattr(logging, args.loglevel.upper(), None)
    if not isinstance(numeric_loglevel, int):
        raise ValueError('Invalid log level: {}'.format(loglevel))
    logging.basicConfig(level=numeric_loglevel,
                        format='[%(levelname)s]\t%(message)s'
    )

    

    main(args)
