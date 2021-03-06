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

    - allows /dictionaries of submissions/ in
      submissions.$assignment_name.$partiticipant_name

    - consequently, submission filenames change to
      ${partiticipant_name}-${assignment_name}#${submission_id}.$suffix
      where ${submission_id} is an identifier string

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

def make_program_name(participant_name, submission_name, submission_id):
    if submission_id is None or submission_id=="":
        return "-".join([participant_name,submission_name])
    else:
        return "{}-{}#{}".format(participant_name,submission_name,submission_id)

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

def enumerate_tests(participant_name, assignment, submission_id, the_tests):
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
        the_tests.append([participant_name,assignment,submission_id,test_id,test])

def check_call_bash_script(shell_script):
    """Run bash shell script after wrapping it in bash call
    @param shell_script multiline shell script as list of lines
    """
    logging.debug("Execute shell script\n"
                  +"\n".join(shell_script))
    wrapped_shell_script = ("bash -s <<EOF\n"
                    + "\n".join(shell_script)
                    + "\nEOF")
    subprocess.check_call(wrapped_shell_script,shell=True)


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

        def singlequote(s):
            return " ".join(map( lambda x: "'"+x+"'", s.split(" ")))

        conda_create_command="conda create"
        if not logging.getLogger().isEnabledFor(logging.DEBUG):
            conda_create_command += " >/dev/null"
        conda_create_command += " -y -n "+conda_env_name+" "+singlequote(language["conda-install"])

        logging.debug("  by running "+conda_create_command)

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
                       submission_id,
                       the_conda_environments,
                       configuration):
    """
    Run the compilation for a submission
    @param submission the submission dictionary (of a participant)
    @param configuration the configuration
    @return success status
    """
    
    logging.debug("Compile submission "+submission_name
                  +" "+str(submission_id)
                  +" of "+participant_name)

    submission=configuration["submissions"][participant_name][submission_name][submission_id]
    assignment=lookup_assignment(submission_name,configuration)

    language_name = get_submission_language(submission)
    language = configuration["languages"][language_name]

    directory=assignment["directory"]
    
    if "compile" in language:
        prog_name = make_program_name(participant_name, submission_name, submission_id)
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

        try:
            logging.info("Compile "+prog_name)
            check_call_bash_script(shell_script)
        
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
    @param test_spec = [participant_name, assignment, submission_id, test_id, test]
    @subparam participant_name name of the participant
    @subparam assignment the assignment record
    @subparam test_id index of the test
    @subparam test dictionary of the test
    @param test_results hash of the test results
    @param configuration the entire configuration

    @todo merge with run_test
    """

    [participant_name, assignment, submission_id, test_id, test] = test_spec

    assignment_name = assignment["name"]
    
    status="OK" # be optimistic;)
    fail_status = "failed" if get_feature(test,"optional",False) else "FAILED" 
   
    timeout=get_feature(test,"timeout",None)

    assignment_name = assignment["name"]
    submission = configuration["submissions"][participant_name][assignment_name][submission_id]

    test_descr=str(test_id+1)
    if not "name" in test:
        logging.warn("Missing name in test "+test_descr+" of assignment '"+assignment_name+"'.")
    else:
        test_descr = test["name"]
    test_descr = test_descr

    directory = assignment["directory"]
        
    program_name = make_program_name(participant_name, assignment_name, submission_id)
    
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
                shell_script.append("export LD_LIBRARY_PATH=$HOME/miniconda3/envs/"+conda_env_name+"/lib")

        shell_script.append("cd "+directory)
        shell_script.append("set -o pipefail")
        
        if timeout is not None:
            timeout_call = "timeout " + timeout + " "
        else:
            timeout_call = ""

        program_call_command = (program_call
                                +" {arguments} {infile} >{genfile}".format(**testcall_params))

        check_command = "diff -d -y --suppress-common-lines {genfile} {outfile} | head -n10".format(**testcall_params)
        if exists_and_defined("check", test):
            check_command = test["check"].format(**testcall_params)

        logging.info("Program call: "+program_call_command)
        if timeout is not None:
            logging.info("Timeout: "+timeout)

        program_call_command = ("time "
                                +timeout_call
                                + program_call_command)
        check_call_bash_script(shell_script+[program_call_command])

        logging.info("Check by: "+check_command)
        check_call_bash_script(shell_script+[check_command])
        
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
        "submission_id": submission_id,
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

def check_submission(participant_name, submission_name, submission_id, configuration):
    """
    Check submission configuration
    
    checks whether program exists, correct language specified etc...
    @return whether submission is valid for testing
    """

    logging.debug("Check validity of submission "+str(submission_name)
                  +" "+str(submission_id)
                  +" of "+participant_name
                  +" in "+str(configuration["submissions"])
    )

    submission = configuration["submissions"][participant_name][submission_name][submission_id]

    logging.debug("Check validity of submission "+str(submission_name)
                  +" "+str(submission_id)
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
                                                          submission_id))
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

def isdictofdicts(x):
    return ( isinstance(x,dict)
             and all( [ isinstance(x[y],dict) for y in x ] )
    )

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
    if participant_name in configuration["submissions"]:
        submission = configuration["submissions"][participant_name]
        if submission is None:
            submission = list()

        for submission_name in submission:
            the_submission = submission[submission_name]
            ## we allow dictionary submission entries to support multiple submissions to the same assignment
            ## with different suffixes
            ## At the same time, we still allow single submissions (without dict wrapping).
            ## To handle both cases uniformly, we wrap unwrapped submission entries
            if not isdictofdicts(the_submission):
                the_submission = { None: the_submission }
                configuration["submissions"][participant_name][submission_name] = the_submission
            
            for submission_id in the_submission:                
                # check general validity of participant's submissions
                if check_submission(participant_name, submission_name, submission_id, configuration):
                    # check whether submission needs testing
                    if not exists_and_equals("checked",
                                             the_submission[submission_id],
                                             True):
                        test_assignments.append((submission_name, submission_id))
                else:
                    failed_submissions.append((submission_name, submission_id, "INVALID"))

    if len(test_assignments)>0:
        logging.info("Perform tests for submissions "+str(test_assignments))
    
    test_results=list()

    the_conda_environments=dict()

    # for the un-tested submissions, 
    #   setup conda environments 
    #   and compile if necessary
    for (submission_name, submission_id) in test_assignments:
        submission=configuration["submissions"][participant_name][submission_name][submission_id]
        assignment=lookup_assignment(submission_name,configuration)
        if (not args.skip_depends and 
            not create_conda_env(submission, the_conda_environments, configuration)):
            test_assignments.remove((submission_name, submission_id))
            failed_submissions.append((submission_name, submission_id, "DEPENDENCY_FAILED"))
        elif not compile_submission(participant_name, submission_name, submission_id,
                                    the_conda_environments, configuration):
            test_assignments.remove((submission_name, submission_id))
            failed_submissions.append((submission_name,
                                       submission_id,
                                       "COMPILE_FAILED"))          


    ## determine the tests that we want to perform
    the_tests = list()
    for assignment in configuration["assignments"]:
        for (test_assignment, submission_id) in test_assignments:
            if assignment["name"] == test_assignment:
                enumerate_tests(participant_name, assignment, submission_id, the_tests)
    

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
    
    row_format_string="{participant_name:16} {assignment_name:20} {submission_id:5} {test_description:16} {status:6}"

    if len(test_results)>0 or len(failed_submissions)>0:
        summary_table.append(row_format_string.format(
            participant_name="PARTICIPANT",
            assignment_name="ASSIGNMENT",
            submission_id="ID",
            test_description="TEST",
            status="STATUS"
        ))
        summary_table.append("----------------------------------------------------------")
    
    for entry in test_results:
        if entry['submission_id'] is None: entry['submission_id']=''
        summary_table.append(row_format_string.format(**entry))
        if entry["status"][0:6] == "FAILED":
            all_ok = False
            
    for (submission_name, submission_id, fail_status) in failed_submissions:
        if submission_id is None: submission_id="-"
        summary_table.append(row_format_string.format(
            participant_name=participant_name,
            assignment_name=submission_name,
            submission_id=submission_id,
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
        raise ValueError('Invalid log level: {}'.format(args.loglevel))
    logging.basicConfig(level=numeric_loglevel,
                        format='[%(levelname)s]\t%(message)s'
    )

    main(args)
