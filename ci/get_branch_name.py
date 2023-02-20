import sys

def get_branch_name(branch):
    if "/" in branch:
        branch_name = branch.split('/')[1].lower()
    else:
        branch_name = branch.lower()
    print (branch_name)
    
if __name__ == "__main__":
    get_branch_name(sys.argv[1])