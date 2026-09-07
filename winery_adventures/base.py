"""Common interface for Winery Adventures analyzers."""

from abc import ABC, abstractmethod

import polars as pl


class BaseWineryAnalyzer(ABC):
    """Define the common interface used to process winery data."""

    @abstractmethod
    def analyze_data(self, df: pl.DataFrame) -> pl.DataFrame:
        """Process readings according to the analyzer's responsibility.

        Args:
            df: readings to process.

        Returns:
            A new DataFrame containing the analysis result.

        Raises:
            NotImplementedError: only if a subclass implements the method
                and delegates its execution to this base, for example with
                ``return super().analyze_data(df)``. This is the only case
                in which the body of this method is actually executed.
            TypeError: raised by Python, not by this method, when attempting
                to instantiate ``BaseWineryAnalyzer`` or a subclass that does
                not define ``analyze_data``. The check occurs when the object
                is created, so the error arises before the pipeline
                processes any data.
        """
        raise NotImplementedError


# Possible cases for a subclass of BaseWineryAnalyzer.
# 1. It does not define analyze_data.
#    It inherits the abstract method and remains abstract: Python rejects
#    instantiation with TypeError. The error occurs where the analyzer is
#    constructed (main.py), not where it is used, therefore before reading the TSV files.
# 2. It defines analyze_data but delegates with super().analyze_data(df).
#    The object is created successfully, and the error occurs only when the
#    method is called, as NotImplementedError. This is the only case that executes
#    the abstract method's body, and it is the reason that body exists:
#    without it, delegation would silently return None and the pipeline
#    would pass None to the next analyzer.
# 3. It defines analyze_data with its own implementation.
#    This is the intended case, used by WineryTransformer and WineryHPCComputations.

# Instantiating BaseWineryAnalyzer directly falls under case 1 and produces the
# same TypeError: the class describes a contract, not a usable analyzer.

# WineryPipeline does not check this inheritance: it accepts any object
# with a compatible analyze_data method, as described by the Protocol in
# pipeline.py. The base class documents and enforces the contract for those writing a
# new analyzer; the Protocol describes the minimum requirement for running it.
