# Market ZIP catalog gate

Explicit local GUI operation only. Central directory and fixed EOCD/ZIP64 metadata
are read, never member contents, local headers, Parquet footers or rows. A bounded
view prevents member reads during ZipFile construction. ZIPs with comments,
multi-disk archives and nonstandard ZIP64 extensions are deliberately rejected.
Maximum 128 GiB per archive, 32 MiB central directory, 50,000 entries per archive,
100,000 entries total, 16 MiB receipt. These are initial conservative engineering
limits, not performance measurements. Artificial ZIP64 end records are tested;
multi-gigabyte disk archives are not yet tested. Filename-based reserved labels
are counted but not copied into the receipt. Other Parquet entries are all
LOCKED_UNVERIFIED_PERIOD; filenames do not prove coverage. No archive is opened
to determine the time period, and no market statistics or paths are posted.
A real source partition with independently verified development-only coverage
remains required before research reads. Local metadata is private; do not upload
the receipt. No change to synthetic mailbox, holdout, lease or live-trading scope.
