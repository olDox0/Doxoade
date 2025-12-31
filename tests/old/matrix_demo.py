# tests/matrix_demo.py
import time
import random

def reactor_core(power_level):
    temperature = 100
    status = "STABLE"
    
    print(f"--- INITIATING CORE (Level: {power_level}) ---")
    
    for i in range(5):
        # Simula processamento
        fluctuation = random.randint(-10, 20)
        temperature += (power_level * 2) + fluctuation
        
        if temperature > 300:
            status = "CRITICAL"
            temperature -= 50 # Emergency cooling
        elif temperature > 200:
            status = "WARNING"
        else:
            status = "OPTIMAL"
            
        # Pequena pausa para visualizarmos o fluxo (opcional, o flow já mostra o delay)
        time.sleep(0.1) 
        
    return status, temperature

def main():
    system_ready = True
    initial_power = 10
    
    if system_ready:
        final_status, final_temp = reactor_core(initial_power)
        print(f"Final Report: {final_status} at {final_temp} degrees.")

if __name__ == "__main__":
    main()