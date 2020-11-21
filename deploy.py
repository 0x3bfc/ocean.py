#! ./venv/bin/python3

import brownie
import os
import sys

from ocean_lib import Ocean
from ocean_lib.ocean import util
from ocean_lib.web3_internal.account import Account, privateKeyToAddress

SUPPORTED_NETWORKS_STR = str(util.SUPPORTED_NETWORK_NAMES)[1:-1]

def main():
    network = processArgs()
    s = deploy(network)
    print(s)
    
def processArgs():
    #set help message
    help = f"""
Deploy DataTokenTemplate and more to a target network. 

Usage: deploy.py NETWORK
  NETWORK -- one of: {SUPPORTED_NETWORKS_STR}
 """

    # ****SET INPUT ARGS****
    #got the right number of args?  If not, output help
    num_args = len(sys.argv) - 1
    num_args_needed = 1
    if num_args != num_args_needed:
        print(help)
        if num_args > 0:
            print("Got %d argument(s), need %s.\n" % (num_args, num_args_needed))
        sys.exit(0)
    
    #grab args
    network = sys.argv[1]
    print("Arguments: NETWORK=%s\n" % network)

    #corner cases
    if network not in util.SUPPORTED_NETWORK_NAMES:
        print(f"Invalid network. Supported networks: {SUPPORTED_NETWORKS_STR}")
        sys.exit(0)

    return network

def deploy(network):

    # ****SET ENVT****
    #grab vars
    factory_deployer_private_key = util.confFileValue(network, 'FACTORY_DEPLOYER_PRIVATE_KEY')

    #corner cases 
    if invalidKey(factory_deployer_private_key):
        print("Need valid FACTORY_DEPLOYER_PRIVATE_KEY")
        sys.exit(0)
    
    # ****CONNECT TO EXISTING RUNNING CHAIN****
    assert not brownie.network.is_connected()
    assert network != 'development', "can't have network='development' because brownie reverts that"
    if network in ['rinkeby', 'main']: #set os envvar for infura
        id_ = util.confFileValue('DEFAULT', 'WEB3_INFURA_PROJECT_ID')
        setenv('WEB3_INFURA_PROJECT_ID', id_)
        
    brownie.network.connect(network)
    
    # ****SEE FUNDS****
    print("Keys:\n%s" % Account(private_key=factory_deployer_private_key).keysStr())
    print("")
        
    # ****DEPLOY****
    if network == 'ganache': #past deployments cause errors, so delete them
        os.system(f'rm -rf ./build/deployments/1234')
        
    deployer_account = util.brownie_account(factory_deployer_private_key)
    p = brownie.project.load(f'./', name=f'MyProject')

    print("****Deploy DataTokenTemplate: begin****")
    minter_addr = deployer_account.address
    cap = 2**255
    fee_addr = deployer_account.address
    dt_template = p.DataTokenTemplate.deploy(
        'Template', 'TEM', minter_addr, cap, 'blob', fee_addr, {'from': deployer_account})
    print("****Deploy DataTokenTemplate: done****\n")
        
    print("****Deploy 'DTFactory': begin****")
    fee_addr = deployer_account.address
    dtfactory = p.DTFactory.deploy(
        dt_template.address, fee_addr, {'from': deployer_account})
    print("****Deploy 'DTFactory': done****\n")
    
    print("****Deploy BPool: begin****")
    bpool_template = p.BPool.deploy({'from': deployer_account})
    print("****Deploy BPool: done****\n")
    
    print("****Deploy 'BFactory': begin****")
    bfactory = p.BFactory.deploy(bpool_template.address,
                                 {'from': deployer_account})
    print("****Deploy 'BFactory': done****\n")

    if network == 'ganache':
        print("****Deploy fake OCEAN: begin****")
        #For simplicity, hijack DataTokenTemplate.
        minter_addr = deployer_account.address
        OCEAN_cap = 1410 * 10**6 #1.41B
        OCEAN_cap_base = util.toBase18(float(OCEAN_cap))
        fee_addr = deployer_account.address
        OCEAN_token = p.DataTokenTemplate.deploy(
            'Ocean', 'OCEAN', minter_addr, OCEAN_cap_base, '', fee_addr,
            {'from': deployer_account}) 
        print("****Deploy fake OCEAN: done****\n")

        print("****Mint fake OCEAN: begin****")
        OCEAN_token.mint(minter_addr, OCEAN_cap_base, {'from':deployer_account})
        print("****Mint fake OCEAN: done****\n")

        print("****Distribute fake OCEAN: begin****")
        amt_distribute = 1000
        amt_distribute_base = util.toBase18(float(amt_distribute))
        for key_label in ['TEST_PRIVATE_KEY1', 'TEST_PRIVATE_KEY2']:
            key = util.confFileValue(network, key_label)
            dst_address = privateKeyToAddress(key)
            OCEAN_token.transfer(dst_address, amt_distribute_base,
                                 {'from': deployer_account})
        print("****Distribute fake OCEAN: done****\n")

    s = f"""****Things to update in ~/ocean.conf****"
DTFACTORY_ADDRESS = {dtfactory.address}
BFACTORY_ADDRESS = {bfactory.address}"""
    if network == "ganache":
        s += f"""
OCEAN_ADDRESS = {OCEAN_token.address}"""
    return s

def brownieAccount(private_key):
    assert brownie.network.is_connected()
    return brownie.network.accounts.add(private_key=private_key)

def invalidKey(private_key_str): #super basic check
    return len(private_key_str) < 10

def invalidAddr(addr_str): #super basic check
    return len(addr_str) < 10

def setenv(key, value):
    #os.putenv(key, value) #Do *not* use putenv(), it doesn't work
    os.environ[key] = value

if __name__ == '__main__':
    main()
