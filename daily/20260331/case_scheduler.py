#!/usr/bin/env python3
"""
Case Scheduler - 持续执行 YAML 测试用例的调度程序

采用 OOP 设计模式，实现循环顺序执行指定目录下的所有 YAML 测试用例。
"""

import os
import sys
import subprocess
import logging
import signal
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable
import threading

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from chaos.utils.singleton import SingletonMeta
