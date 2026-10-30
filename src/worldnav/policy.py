"""Small policy boundary shared by API and future local model implementations."""
from abc import ABC, abstractmethod
from .data import Observation


class BasePolicy(ABC):
    @abstractmethod
    def predict(self, observation: Observation, seed: int = 0) -> dict:
        """Return actions in the current robot body frame, without label access."""
        raise NotImplementedError
