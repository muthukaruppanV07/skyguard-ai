import asyncio
import sys
import time
from datetime import datetime

from backend.config import settings
from backend.database.session import init_db, AsyncSessionLocal
from backend.simulation.aws_simulator import AWSSimulator
from backend.simulation.anomaly_injector import AnomalyInjector, SIHDemoScenario
from backend.simulation.demo_scenarios import QuickDemoScenario


async def run_historical_data():
    print("Generating historical data for model training...")
    await AWSSimulator(AsyncSessionLocal()).run_simulation_step(datetime.utcnow())
    print("Use scripts/train_models.py to train models on historical data")


async def run_sih_demo():
    print("=" * 60)
    print("SKYGUARD AI - SIH Demo Mode")
    print("=" * 60)
    
    await init_db()
    
    async with AsyncSessionLocal() as db:
        simulator = AWSSimulator(db)
        await simulator.reset()
        
        injector = AnomalyInjector(db)
        demo = SIHDemoScenario(injector)
        
        print("\nStarting SIH Demo Sequence:")
        print("-" * 40)
        
        for i, step in enumerate(demo.demo_steps):
            print(f"\n[{i+1}/{len(demo.demo_steps)}] {step['name']}")
            print(f"    {step['description']}")
            
            result = await demo.run_step(i)
            print(f"    Status: {result['status']}")
            
            if step['action'] != 'reset':
                await asyncio.sleep(step['duration'])
        
        print("\n" + "=" * 60)
        print("Demo complete!")
        print("=" * 60)


async def run_quick_demo():
    print("=" * 60)
    print("SKYGUARD AI - Quick Demo")
    print("=" * 60)
    
    await init_db()
    
    async with AsyncSessionLocal() as db:
        simulator = AWSSimulator(db)
        await simulator.reset()
        
        injector = AnomalyInjector(db)
        demo = QuickDemoScenario(injector)
        
        print("\nQuick Demo Steps:")
        print("-" * 40)
        
        for i, step in enumerate(demo.demo_steps):
            print(f"\n[{i+1}] {step['name']}: {step['description']}")
            result = await demo.run_step(i)
            print(f"    Result: {result['status']}")
            
            if step['action'] != 'reset':
                await asyncio.sleep(3)
        
        print("\nQuick demo complete!")


async def run_continuous_simulation():
    print("Starting continuous AWS simulation...")
    print("Press Ctrl+C to stop")
    
    await init_db()
    
    async with AsyncSessionLocal() as db:
        simulator = AWSSimulator(db)
        
        try:
            await simulator.start_continuous(interval_seconds=1)
        except KeyboardInterrupt:
            simulator.stop()
            print("\nSimulation stopped")


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.run_demo [historical|sih|quick|continuous]")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    if mode == "historical":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        asyncio.run(run_historical_data())
    elif mode == "sih":
        asyncio.run(run_sih_demo())
    elif mode == "quick":
        asyncio.run(run_quick_demo())
    elif mode == "continuous":
        asyncio.run(run_continuous_simulation())
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)


if __name__ == "__main__":
    main()