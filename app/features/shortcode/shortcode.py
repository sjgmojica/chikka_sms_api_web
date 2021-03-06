'''
    @author: jhesed tacadena
    @description:
        - shortcode.py contains functions
        that is used to generate, validate, 
        and save unique shortcodes
    @year: 2013
'''

from re import match
from random import choice, randint
from models.account import Account
from models.suffixes import Suffixes, DuplicateSuffixException
from models.content_providers import ContentProviders
from features.shortcode.exceptions import *
import features.logging as sms_api_logger
from utils.mobile_formatting_util import alpha_to_numeric
from utils.code_generation import create_client_id, create_sha256_signature

RANDOM_STRING = '0123456789' 
MIN_CODE_LEN = 3 
CODE_LIST_LEN = 20
ALLOWED_CODE = "^[A-Za-z0-9]*$"
MAX_CODE_GEN_TRIES = 2
CODE_LEN = 6

# ------------------------------
# Functions called by handlers
# ------------------------------

def process_code_list_generation(account_id, starts_with):
    '''
        @description:
            - encapsulates the whole
            shortcode generation process.
            - this will be the only function called
            by the handlers if they need a shortcode list
    '''
    
    gen_logger = sms_api_logger.GeneralLogger()    
    
    # is shortcode valid format?
    
    if not match(ALLOWED_CODE, starts_with):
        gen_logger.error('Invalid shortcode', {'account_id': account_id,
            'shortcode_tried': starts_with})
            
        raise ShortcodeFormatInvalidException(
            account_id, starts_with)
                    
    starts_with = alpha_to_numeric(starts_with)
    code_list = __generate_shortcode_list(account_id, starts_with) 
    tries = 0
    
    # the code list generated may contain less than 10
    # shortcodes (i.e. the generated shortcode was already
    # taken). These loop ensures that the system tried
    # atleast MAX_CODE_GEN_TRIES before returning a
    # code list with less than 10 shortcodes
    
    while tries < MAX_CODE_GEN_TRIES and \
        type(code_list) == list and \
        len(code_list) < 10:
        
        if tries > 0:    
            gen_logger.info('shortcode generated less than 10. Trying to regenerate MORE codes',
                {'account_id': account_id, 'tries': tries,
                'shortcode_tried': starts_with})
                
        if len(code_list) > 0:
            code_list.extend(
                __generate_shortcode_list(account_id, starts_with, 
                    code_list))
        tries += 1
      
    if not code_list:
        gen_logger.error('No shortcode match', {'account_id': account_id,
            'shortcode_tried': starts_with})
            
        raise NoShortcodeMatchException(account_id, starts_with)
    
    return __trim_code_list(code_list)
  
def process_shortcode_claiming(account_id, email, status, shortcode):
    '''
        @description:
            - handles the claiming of shortcodes
            
            
        steps done in process
        
        1. check if user already has short code
        
        2. check short code format
        
        3. save shortcode suffix in account record
        
        4. save shortcode suffix in claimed suffixes
            
        5. update account suffix cache
    '''
    gen_logger = sms_api_logger.GeneralLogger()
    gen_logger.info("start assign access code process", {"account_id":account_id, "suffix" : shortcode, 'current_status' : status, 'email': email})

    if shortcode.isalpha():
        shortcode = alpha_to_numeric(shortcode)
    
    # double check if suffix is already taken
    suffix_is_reserved_or_used = Suffixes.check_suffix_list_availability( suffix_list=[shortcode] )
    if suffix_is_reserved_or_used:
        gen_logger.error("suffix is already used/reserved", {"suffix": shortcode, "account_id":account_id})
        raise Exception("suffix is already used/reserved")
    
    # do not process if user already has shortcode
    is_use_result = account_has_shortcode(account_id) 
    if is_use_result:            
        # logging is in function itself. bec. being used
        # by outside scripts
        gen_logger.error("access code suffix is already assigned to user", {'suffix': is_use_result })
        raise HasSuffixException(account_id)

    try:
        gen_logger.error('saving suffix to account', {'account_id':account_id, 'suffix': shortcode})
        __update_suffix(account_id, shortcode)
        
        # verify that the account saved the suffix
        account_object = Account.get( account_id = account_id )
        if not account_object:
            gen_logger.error('account not available', {'account_id':account_id})
            raise Exception('not found')

        if account_object.suffix != shortcode:
            gen_logger.error("could not save suffix to account. there may be a duplicate record", {"account_id": account_id, "suffix":shortcode})
            raise Exception('suffix %s not saved to account' % shortcode)
        
    except DuplicateSuffixException, e:
        gen_logger.error('Shortcode unavailable', 
            {'account_id': account_id,
            'shortcode': shortcode})   
                        
        raise DuplicateSuffixException(shortcode)
    
    except Exception, e:
        gen_logger.error('exception raised while saving suffix to account record', {'exception': e})
        raise Exception('could not save access code to account', {'suffix' : shortcode})
    
    else:
        # continue with process
        
        # if status == 'PENDING' or status == 'None' or not status:
        if status == 'None' or not status or status == 'NULL':
            __update_acct_package(account_id, package='FREE')
            
            
            ContentProviders.set_api_trial_credits(shortcode)
            
            # sets TRIAL_CREDITS = CREDITS_COUNT (i.e. 20) in INFRA's redis
               
            # create CLIENT KEY AND SECRET
    
            client_id = create_client_id(email=email)
            secret_key = create_sha256_signature(
                suffix=shortcode, email=email)
            
            gen_logger.info("client is entering FREE state. assigning client id and secret key for first time", { "suffix": shortcode, "account_id":account_id, "client_id":client_id, "secret_key":secret_key})
    
            ContentProviders.update_cached_api_settings(
                suffix=shortcode, client_id=client_id, secret_key=secret_key)
                
            ac_obj = Account()
            ac_obj.update(account_id=account_id,
                client_id=client_id, 
                secret_key=secret_key)
                
        elif status == 'INACTIVE': # ! TEMP @todo !
            gen_logger.info("client is INACTIVE entering UNPAID state", { "suffix": shortcode, "account_id":account_id})
            
            __update_acct_package(account_id, package='UNPAID')
            ac_obj = Account.get(account_id=account_id)        
            ContentProviders.update_cached_api_settings(
                suffix=shortcode, client_id=ac_obj.client_id, 
                secret_key=ac_obj.secret_key, active='1')
                

def generate_shortcode(starts_with='', should_be_unique=False):
    '''
        @description:
            - generates a shortcode based on
            @param starts_with and defined
            - @param should_be_unique:
                determines if the generated code
                should not be in the DB
    '''
    MAX_CODE_LEN = 6
    code_len_to_generate = 3
    
    if starts_with:
        MAX_CODE_LEN -= len(starts_with)
        code_len_to_generate -= len(starts_with)
        if code_len_to_generate < 0:
            code_len_to_generate = 1
       
    rand_code = ''.join(choice(RANDOM_STRING)
        for i in range(randint(code_len_to_generate, MAX_CODE_LEN)))
    rand_code = starts_with + rand_code
    
    if should_be_unique:
        if Suffixes.get_suffix(suffix=rand_code): 
            generate_shortcode(starts_with, True)
        
    return rand_code
    
def account_has_shortcode(account_id):
    '''
        @description:
            - returns True if user already has shortcode,
            else False
    '''
    
    # gen_logger = sms_api_logger.GeneralLogger()    
    suffix = Suffixes.has_suffix(account_id)
    
    if suffix and suffix['suffix']:
        # before: true, but due to changing business 
        # rule, now returning suffix
        # gen_logger.error('User has shortcode', 
            # {'account_id': account_id, 'existing_code': suffix}) 
        return suffix['suffix']  
    
    return False
   
def is_shortcode_valid(code):
    '''
        @description:
            - returns True if shortcode
            is valid, else False
    '''
    if len(code) > CODE_LEN or len(code) < MIN_CODE_LEN:
        return False
    if not match(ALLOWED_CODE, code):
        return False
    return True
    
# *************************************
# *************************************
# The functions from here on are
# mini functions used by the public functions 
# above. Please use with care if an
# outside handler will try to use these
# *************************************
# *************************************

# --------------------------------------
# used by process_code_list_generation
# --------------------------------------

def __generate_shortcode_list(account_id, starts_with='', 
    precomputed_shortcode_list=None):
    '''
        @description:
            - generates a list of shortcodes.
            - @param precomputed_shortcode_list:
                used only when the length of the 
                first batches of generated 
                shortcode lists after being 
                compared to DB is < 10.
            - the maxtries variable here is the 
            terminating condition which will be
            used in rare cases (i.e. if all
            the possible shortcodes based on 
            @param starts_with are already taken)
    '''
    
    i = 0
    max_tries = 50 # maximum random code generation
    code_list = []
    
    if starts_with and not precomputed_shortcode_list and len(starts_with) >= MIN_CODE_LEN:
        # just being sure that the searched 
        # suffix is included in list
        code_list.append(starts_with)
    
    # return the searched suffix if its
    # length is already 6
    if len(starts_with) == 6:
        return __remove_used_codes(code_list)
          
    # --- Generates Random codes based on @param starts_with ---
    
    while i < CODE_LIST_LEN:
        code = generate_shortcode(starts_with)
        if code not in code_list and ((precomputed_shortcode_list and \
            code not in precomputed_shortcode_list) \
            or not precomputed_shortcode_list):  
            code_list.append(code)
            i += 1
        max_tries -= 1
        
        # terminating condition for some RARE cases
        if max_tries <= 0:
            i = CODE_LIST_LEN
    
    # --- REMOVES USED SUFFIXES IN LIST based on DB ---
    
    code_list = __remove_used_codes(code_list)
    
    if not code_list:
        # raise NoShortcodeMatchException(
                # account_id, starts_with)i
        print 'no code list'
        
    return code_list

def __remove_used_codes(code_list):
    '''
        @description:
            - removes the suffix(es) from
            @param code_list if it/these
            are already taken
    '''
    # TESTING ONLY: these two should be removed from list
    # code_list.append('1234')
    # code_list.append('123')
    # END TEST
   
    taken_suffixes = Suffixes.check_suffix_list_availability(
        suffix_list=code_list)
  
    if taken_suffixes:
        for taken_suffix in taken_suffixes:
            code_list.remove(str(taken_suffix['suffix']))
    
    return code_list

def __trim_code_list(code_list):
    '''
        @description:
            - trims code list, if its
            length is > 10
    '''
    
    if len(code_list) >= 10:
        return code_list[0:10]
    return code_list
        
    
# --------------------------------------
# used by process_shortcode_claiming
# --------------------------------------


def __update_suffix(account_id, suffix):
    '''
        @description:
            - updates suffix in accounts table
    '''
    Account.update_suffix(
        account_id=account_id, suffix=suffix)
    Suffixes.set_suffix(
        account_id=account_id, suffix=suffix)

            
def __update_acct_package(account_id, package):
    '''
        @description:
            - updates package in accounts table
    '''
    return Account.update(account_id=account_id,
        package=package)
        