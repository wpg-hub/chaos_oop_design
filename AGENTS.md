# AGENTS.md

## Key Commands

```bash
# Run case (single or directory)
python3 chaos/main.py case --name cases/examples/network_delay.yaml
python3 chaos/main.py case --dir cases/

# Clear effects
python3 chaos/main.py clear --env all --type all

# State management
python3 chaos/main.py state --action list
python3 chaos/main.py state --action clear

# Workflow execution
python3 chaos/main.py workflow --file workflows/serial_example.yaml
python3 chaos/main.py workflow --dir workflows/ --dry-run

# Version
python3 chaos/main.py version --action show
./scripts/version_iterate.sh
```

## Tests

```bash
python3 -m pytest
python3 -m pytest tests/test_network_delay_injector.py -v
```

## Architecture

- Entry: `chaos/main.py` - CLI via argparse
- Config: `config.yaml` - SSH credentials (4 nodes), BMC, switch configs
- Cases: `cases/` - YAML files describing fault injection scenarios
- Workflows: `workflows/` - Serial/parallel/hybrid workflow definitions

## Important Notes

- SSH credentials in `config.yaml` are real - do not commit changes exposing credentials
- Pod types: ddb (distributed database), sdb, etcd, upc, upu, rc
- Fault types: network (delay, loss, corrupt, duplicate, reorder), pod (delete, stop), process (kill), computer (reboot, ipmitool)
- Workflows use `--file` and `--dir` as mutually exclusive options