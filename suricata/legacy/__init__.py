"""Quarentena de legados do Suricata.

Módulos legados cobertos por testes (delivery, whatsapp, lease, grupo)
vivem aqui. As origens (suricata/delivery.py, suricata/notifiers/whatsapp.py,
suricata/lease.py, suricata/grupo.py) são facades de compatibilidade que
re-exportam exatamente os mesmos objetos. Remoção proibida sem prova de
equivalência — ver ARCHITECTURE.md §6.1.
"""
