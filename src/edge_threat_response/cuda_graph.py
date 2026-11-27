"""Single-shape CUDA Graph replay for the native PyTorch detector forward."""

from __future__ import annotations

from typing import Any, Callable


class FixedCudaGraphForward:
    def __init__(self, forward: Callable[..., Any]) -> None:
        self._forward = forward
        self._graph: Any | None = None

    @property
    def captured(self) -> bool:
        return self._graph is not None

    def __call__(self, image: Any, *args: Any, **kwargs: Any) -> Any:
        if args or kwargs.get("augment") or kwargs.get("embed"):
            raise ValueError("CUDA Graph requires fixed native inference arguments.")
        if not image.is_cuda:
            raise ValueError("CUDA Graph requires a CUDA input tensor.")
        signature = (image.shape, image.stride(), image.dtype, image.device)
        if self._graph is None:
            self._capture(image, kwargs)
            self._signature = signature
            self._kwargs = kwargs.copy()
            return self._output
        if signature != self._signature or kwargs != self._kwargs:
            raise ValueError("CUDA Graph input shape, layout, device, or arguments changed.")
        self._input.copy_(image)
        self._graph.replay()
        return self._output

    def _capture(self, image: Any, kwargs: dict[str, Any]) -> None:
        import torch

        static_input = image.clone(memory_format=torch.preserve_format)
        stream = torch.cuda.Stream(device=image.device)
        current = torch.cuda.current_stream(image.device)
        stream.wait_stream(current)
        with torch.cuda.stream(stream):
            for _ in range(3):
                eager = self._forward(static_input, **kwargs)
        current.wait_stream(stream)
        eager_tensor = eager[0] if isinstance(eager, (tuple, list)) else eager
        reference = eager_tensor.detach().clone()
        torch.cuda.synchronize(image.device)
        graph = torch.cuda.CUDAGraph()
        with torch.cuda.graph(graph, stream=stream):
            output = self._forward(static_input, **kwargs)
        graph.replay()
        captured_tensor = output[0] if isinstance(output, (tuple, list)) else output
        if not torch.equal(reference, captured_tensor):
            raise RuntimeError("CUDA Graph prediction differs from the eager forward.")
        self._input, self._output, self._graph = static_input, output, graph
