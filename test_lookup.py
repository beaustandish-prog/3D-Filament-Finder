from utils.lookup import lookup_filament_code

print("--- Testing '10100' ---")
res1 = lookup_filament_code("10100")
print(f"Result 1: {res1}\n")

print("--- Testing '13612' (Bambu Teal) ---")
res2 = lookup_filament_code("13612")
print(f"Result 2: {res2}\n")
