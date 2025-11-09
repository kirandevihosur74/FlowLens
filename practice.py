
from collections import defaultdict


def calculate_diff(ingredients_count_party, min_ingredients_party):
    for item in min_ingredients_party:
        if ingredients_count_party[item] < min_ingredients_party[item]:
            min_ingredients_party[item] = min_ingredients_party[item] - ingredients_count_party[item]   
            print(min_ingredients_party[item], "pass1")
    return min_ingredients_party

def has_enough_items(ingredients_count, min_ingredients_count):
    for item in min_ingredients_count:
        if ingredients_count[item] < min_ingredients_count[item]:
            return False
    return True

def get_sandwiches(ingredients):

    # ingredients_count to keep count of all the ingredients
    ingredients_count = defaultdict(int)

    #min_ingredients_count to keep min count the ingredients
    min_ingredients = {'ham':1, 'bread': 1, 'cheese': 1}

    sandwiches = 0
    
    for item in ingredients:
        ingredients_count[item] +=1
        check = has_enough_items(ingredients_count, min_ingredients)

        if check:
            sandwiches+=1
            print("Sandwiches are ready")

            for item in min_ingredients:
                ingredients_count[item] -= min_ingredients[item]
    
    print(f"Total number of sandwiches: {sandwiches}")

if __name__ == "__main__":
    # ingredients  = ['bread', 'bread', 'bread',  'ham', 'cheese', 'bread','ham', 'cheese']
    # ingredients = []

    with open("test.txt", "r") as f:
        ingredients = f.read().splitlines()
        print(ingredients)
    get_sandwiches(ingredients)
