import os
from scripts.courier_founder_mode import FounderModeMVP
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
from scripts.courier_real_worker_adapters import get_real_worker_adapters

dispatcher = CourierSafetyDispatcher(".")
adapters = get_real_worker_adapters()
for name, func in adapters.items():
    dispatcher.adapter_boundary.register_consumer(name, func)

founder = FounderModeMVP(".", dispatcher)
founder.run_autonomous_loop()
