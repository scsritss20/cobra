# -*- coding: utf-8 -*-

"""
    pickup.git
    ~~~~~~~~~~

    Implements various git methods

    :author:    Feei <feei@feei.cn>
    :author:    Lightless <root@lightless.me>
    :homepage:  https://github.com/wufeifei/cobra
    :license:   MIT, see LICENSE for more details.
    :copyright: Copyright (c) 2017 Feei. All rights reserved
"""

import os
import re
import subprocess
from urllib import quote
from cobra.utils.config import home_path, Config
from cobra.utils.log import logger


class GitError(Exception):
    def __init__(self, message):
        Exception.__init__(self)
        self.message = message

    def __str__(self):
        return repr(self.message)


class NotExistError(GitError):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class AuthError(GitError):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class Git(object):
    """
    A Git class.
    You can clone, pull, diff the repo via this class.

    repo_address: the repo's url
    repo_directory: the repo's local path
    repo_username: the username for the repo's url
    repo_password: the password for the repo's password
    repo_branch: the repo branch
    """

    repo_address = None
    repo_directory = None
    repo_username = None
    repo_password = None
    repo_branch = None
    repo_author = None
    repo_name = None

    # https://github.com/<username>/<reponame>

    def __init__(self, repo_address, branch='master', username=None, password=None):

        # get upload directory
        self.upload_directory = os.path.join(home_path, 'versions')
        if os.path.isdir(self.upload_directory) is False:
            os.makedirs(self.upload_directory)

        self.repo_address = repo_address
        self.repo_username = username
        self.repo_password = password
        self.repo_branch = branch
        repo_user = self.repo_address.split('/')[-2]
        repo_name = self.repo_address.split('/')[-1].replace('.git', '')
        self.repo_author = repo_user
        self.repo_name = repo_name

        self.repo_directory = os.path.join(os.path.join(self.upload_directory, repo_user), repo_name)

    def pull(self):
        """Pull a repo from repo_address and repo_directory"""
        logger.info('pull repository...')

        if not self.__check_exist():
            return False, 'No local repo exist. Please clone first.'

        # change work directory to the repo
        repo_dir = self.repo_directory
        logger.debug('cd directory: {0}'.format(repo_dir))
        os.chdir(repo_dir)

        cmd = 'git pull origin master'
        p = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        (pull_out, pull_err) = p.communicate()
        logger.info(pull_out)
        logger.info(pull_err)

        self.parse_err(pull_err)

        pull_err = pull_err.replace('{0}:{1}'.format(self.repo_username, self.repo_password), '')

        # change work directory back.
        os.chdir(repo_dir)

        if 'Updating' in pull_out or 'up-to-date' in pull_out:
            logger.info('pull done.')
            return True, None
        else:
            return False, pull_err

    def clone(self):
        """Clone a repo from repo_address
        :return: True - clone success, False - clone error.
        """
        logger.info('clone repository...')
        if self.__check_exist():
            logger.info('repository already exist.')
            return self.pull()
            # call(['rm', '-rf', self.repo_directory])

        # if no username or password provide, it may be a public repo.
        if self.repo_username is None or self.repo_password is None:
            # public repo
            clone_address = self.repo_address
        else:
            # private repo
            clone_address = self.repo_address.split('://')[0] + '://' + quote(self.repo_username) + ':' + \
                            self.repo_password + '@' + self.repo_address.split('://')[1]
        # clone repo with username and password
        # "http[s]://username:password@gitlab.com/username/reponame"
        # !!! if add password in the url, .git/config will log your url with password
        cmd = 'git clone ' + clone_address + ' "' + self.repo_directory + '" -b master'

        p = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        (clone_out, clone_err) = p.communicate()
        logger.info(clone_out)
        logger.info(clone_err)

        self.parse_err(clone_err)

        clone_err = clone_err.replace('{0}:{1}'.format(self.repo_username, self.repo_password), '')

        logger.info('clone done. Switching to branch ' + self.repo_branch)
        # check out to special branch
        if self.checkout(self.repo_branch):
            return True, None
        else:
            return False, clone_err

    def diff(self, new_version, old_version, raw_output=False):
        """
        Diff between two version, in SHA hex.
        :param new_version: the new version in SHA hex.
        :param old_version: the old version in SHA hex.
        :param raw_output: True-return raw git diff result, False-return parsed result, only add content
        :return: the diff result in str, raw or formatted.
        """
        if not self.__check_exist():
            logger.info('No local repo exist. Please clone it first.')
            return False

        # change the work directory to the repo.
        current_dir = os.getcwd() + os.sep
        repo_dir = current_dir + self.repo_directory
        os.chdir(repo_dir)

        cmd = 'git diff ' + old_version + ' ' + new_version
        p = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        (diff_out, diff_err) = p.communicate()
        logger.info(diff_out)

        # change the work directory back.
        os.chdir(current_dir)
        logger.info('diff done.')
        if raw_output:
            return diff_out
        else:
            return self.__parse_diff_result(diff_out)

    def checkout(self, branch):
        """
        Checkout to special branch.
        :param branch: branch name
        :return: True-checkout success or already on special branch
                 False-checkout failed. Maybe no branch name.
        """
        if not self.__check_exist():
            logger.info('No repo directory.')
            return False

        current_dir = os.getcwd()
        os.chdir(self.repo_directory)

        cmd = "git checkout " + branch
        p = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        (checkout_out, checkout_err) = p.communicate()
        logger.info(checkout_err)

        # Already on
        # did not match
        # Switched to a new branch
        if 'did not match' in checkout_err:
            os.chdir(current_dir)
            return False
        else:
            os.chdir(current_dir)
            return True

    def __check_exist(self):
        """check if the repo has already cloned.
        :returns bool
            True : the repo already exist.
            False : the repo do not exist.
        """
        if os.path.isdir(self.repo_directory):
            return True
        else:
            return False

    def __parse_diff_result(self, content):
        """parse git diff output, return the format result
        :return: a dict, each key is the filename which has changed.
                 each value is a list store every changes.
        example:
                {'bb.txt': ['hhhhhhh'], 'aa.txt': ['ccccc', 'ddddd']}
                bb.txt add a line, the content is 'hhhhhhh'.
                aa.txt add two line, the content is 'ccccc' and 'ddddd'.
        """
        result = {}
        content = content.split('\n')
        tmp_filename = ''
        for x in content:
            if x != '' and x[0:3] == '+++':
                tmp_filename = x.split('/')[-1]
                result[tmp_filename] = []
            elif x != '' and x[0] == '+':
                if x[1:] != '':
                    result[tmp_filename].append(x[1:])

        return result

    def get_repo(self):
        """
        clone or pull the special repo.
        If the repo already exist in the "uploads" folder, it will pull the repo.
        If there is no repo in "uploads" folder, it will clone the repo.
        :return:
        """
        if self.__check_exist():
            logger.info('repo already exist. Try to pull the repo')
            return self.pull()
        else:
            return self.clone()

    @staticmethod
    def parse_err(err):
        if 'not found' in err or 'Not found' in err:
            raise NotExistError('Repo doesn\'t exist')
        elif 'already exists' in err:
            return False, 'repo has already cloned.'
        elif 'Authentication failed' in err:
            raise NotExistError('Authentication failed')

    @staticmethod
    def committer(file, path, line_number, length=1):
        """
        git blame -L21,+1 -- git.py
        362d5798 (wufeifei 2016-09-10 12:19:44 +0800 21) logging = logger.getLogger(__name__)
        (?:.{8}\s\()(.*)\s(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})
        group #1: wufeifei
        group #2: 2016-09-10 12:19:44
        :param file:
        :param path:
        :param line_number:
        :param length:
        :return: group#1, group#2
        """
        os.chdir(path)
        cmd = "git blame -L{0},+{1} -- {2}".format(line_number, length, file)
        p = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        (checkout_out, checkout_err) = p.communicate()
        if len(checkout_out) != 0:
            group = re.findall(r'(?:.{8}\s\()(.*)\s(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})', checkout_out)
            return True, group[0][0], group[0][1]
        else:
            return False, None, None

    def __repr__(self):
        return "<Git - %r@%r>" % (self.repo_username, self.repo_address)


if __name__ == '__main__':
    # test committer
    c_ret, c_author, c_time = Git.committer('cobra.py', '/Volumes/Statics/Project/Company/cobra/', 11)
    print(c_ret, c_author, c_time)
