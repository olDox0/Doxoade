# test_moe.py
from alfagold.hive.hive_mind import HiveMindMoE

print("🔌 Iniciando MoE...")
hive = HiveMindMoE()
print("🤖 Gerando...")
resultado = hive.run_sequence("def teste")
print(f"\n📝 Resultado: def teste{resultado}")