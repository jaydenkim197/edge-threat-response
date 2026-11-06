# Context-Aware Edge AI Threat Response System

**English research overview — status as of 6 November 2026**

This is a non-commercial undergraduate capstone project at **Yeungnam University, South Korea**, in Fall 2026. We are developing a Jetson-based research prototype to investigate whether person–knife spatial association, temporal confirmation, and learned holding assessment can reduce unnecessary alerts compared with detection-only evidence.

Contact: [22211897@yu.ac.kr](mailto:22211897@yu.ac.kr). See the [repository overview](../README.md) for the Korean introduction and engineering entry points.

## Research problem and intended setting

Our target is a fixed indoor surveillance camera mounted approximately **3 m above the floor**, looking downward at an angle in a corridor, entrance, or shared space. The development hardware is an **NVIDIA Jetson Orin Nano** and a **Reolink P430** camera. The camera pilot does not establish performance at the target mounting geometry.

Small knives, partial occlusion, compression, and unfamiliar viewpoints remain difficult. Close-up and general web images do not establish performance on distant CCTV knives; additional real CCTV imagery is needed.

We study **person-associated knife events**, not violent intent or criminal behavior. Geometry alone does not prove possession. The separate Holding/Not Holding model has not yet been evaluated on real annotated relationships.

## System and comparison design

The full B3/B4 pipeline is:

```text
Camera or recorded video
  -> Person / Knife Detector
  -> Spatial Association (B3) or Learned Holding Assessment (B4)
  -> K-of-N Temporal Confirmation
  -> CLEAR / CANDIDATE / CONFIRMED / COOLDOWN
  -> Alarm Output + Event Metadata + Snapshot
```

Physical GPIO integration is pending; current hardware tests use a mock alarm. Events are recorded on entry to `CONFIRMED`, with cooldown/rearming.

The planned controlled comparison separates detector development from event-decision evaluation:

| Mode | Evidence used to confirm an event |
|---|---|
| B0 | Detection-only, single-frame knife evidence |
| B1 | Knife detection with temporal confirmation |
| B2 | Person–knife spatial association |
| B3 | Spatial association with temporal confirmation |
| B4 | Learned Holding/Not Holding assessment with temporal confirmation |

All modes use a common alert-state framework. The final event comparison will use **the same frozen detector, recordings, and detection JSONL**, with a common temporal configuration where applicable and the same event-matching protocol. B4 adds a separate relationship-score file linked to detector, frame, and classifier hashes. Detector improvement and B3-to-B4 decision improvement are evaluated as separate questions.

Holding prototypes use geometry or person–knife union crops plus geometry. Real annotations distinguish `holding`, `not_holding`, and `uncertain`; uncertain cases are excluded. Image-quality review does not substitute for relationship labels.

## Evaluation and reproducibility

The planned primary outcomes are **event precision/recall/F1, false alerts per hour, and alert delay**. Detector diagnostics additionally report box precision/recall, AP, small-knife recall, and false positives on verified negative images. Box metrics, event metrics, and physical camera-to-GPIO latency are distinct measurements.

We preserve original sources and record dataset versions, class maps, SHA-256 hashes, split/group assignments, configuration, source commit, and raw results. Duplicate checks and source/session grouping help prevent leakage. Frames, crops, augmentations, and simultaneous views of the same staged event stay in one partition. Proxy groups do not prove complete source independence.

Already opened public development sets are used for diagnosis, not claimed as unseen final tests. Target-camera train/tuning sessions and an independent final recording session are planned separately. Thresholds and model selection will be frozen before the final event evaluation.

## What has been completed

| Area | Evidence and limits |
|---|---|
| Decision software | Spatial association, K-of-N, the state machine, B0–B3 replay, event evaluation, metadata, and snapshots have PC/synthetic verification. [Architecture](architecture.md), [verification record](verification.md). |
| Detector training | Four exploratory SOHAS-based and SOHAS/Dangerous Items/Catargiu mixture runs (RAW-R1-n, RAW-H1-n, RAW-M1-n, RAW-M1-s) completed 50 epochs and 35,600 optimizer updates each. Eight model conditions were compared on six development sets; M1-n is a candidate, not the final detector. [Results and limitations](../reports/evaluation/raw-detector-selection-2026-11-06/report.md). |
| Actual Orin camera integration | P430 main/sub RTSP input and YOLO26n/B3 each processed 300 valid frames on Orin using the earlier RAW-R1-n development checkpoint. Metadata/snapshots, mock alarms, and live monitor display were verified; accuracy and physical GPIO were not. [Hardware report](../reports/runtime/p430-yolo26n-2026-11-05/report.md). |
| HOI/B4 implementation | G/VG model loading, relationship scores, replay, and snapshot integration have synthetic checks, including CUDA inference on Orin. Real relationship annotations, training, and accuracy remain pending. [Annotation contract](hoi-annotation-contract.md), [integration evidence](../reports/runtime/hoi-b4-integration-2026-11-05/report.md). |
| GPU training environments | Additional RTX 3060 hosts have matching package versions and passed CUDA FP32/AMP training and checkpoint-reload smoke tests. This is environment verification. [PC14](../reports/training/pc14-cuda-readiness-2026-11-06/report.md), [PC11/PC12](../reports/training/pc11-pc12-cuda-readiness-2026-11-06/report.md). |

The main unresolved detector issue is real CCTV generalization. On an opened development subset of **83 CCTV images with 31 annotated knives**, M1-n at input size 640 detected **0/31** at confidence 0.25 and IoU 0.5; the same checkpoint at 960 detected **1/31**. This correlated development subset motivates target-domain data collection; it is not an independent final test. [Expanded evaluation and protocol](../reports/datasets/reviewed-next-training-2026-11-06/report.md).

Published numbers are exploratory development results with stated limitations. No final independent CCTV event performance or validated real-world threat-detection capability is claimed.

## Additional research data and handling commitments

We seek full-frame real CCTV images containing people and small or occluded knives for detector adaptation or external image-level evaluation, **as agreed with the provider**. Weapon boxes, camera/session identifiers, annotation guidance, and use terms would be useful. The data role is recorded before import; person boxes and Holding labels require separate verification or permitted annotation.

For newly provided restricted data, our commitments are:

1. **Agreed academic use:** follow the provider's written conditions, permitted users, and approved training/evaluation scope. Record source, version, and any restrictions before import.
2. **Private handling:** do not commit restricted originals, derived images, or private annotations to GitHub or publish them through public endpoints. Establish appropriate access controls before ingestion. Any authorized copies on training hosts must remain within the provider's permitted scope.
3. **No unauthorized redistribution:** do not redistribute the dataset or publish example images without explicit permission. Attribution, result publication, and model/checkpoint release must also follow the agreed terms.
4. **Preservation and traceability:** keep original files unchanged and separate source data, working copies, and outputs. Track derived labels and transformations with hashes and versions.
5. **Evaluation separation:** protect held-out sources and recording groups. A set used for model selection will not subsequently be presented as an unseen final test.
6. **Retention and consent:** record retention/deletion and access requirements before import. Follow those terms for storage and backups. Planned local recordings use staged scenarios and props; participant consent and recording/retention conditions are checked before collection.

These commitments do not imply that a restricted-data service is already deployed. The **existing review service is publicly reachable and uses self-selected names**; it is not access control for restricted material. A provider-approved private access arrangement is required before such material can enter a review service.

A separate **legacy submodule contains historical images and checkpoints**, with source-level permission checks separate from this request. Public availability is not treated as permission to reuse or redistribute data. See the [legacy asset record](legacy-asset-selection.md); this overview does not certify its dataset licensing.

## Remaining work and target schedule

Next are a focused real-data detector improvement candidate, target-camera recordings and box/Holding labels, adaptation and HOI training, then model integration. Physical GPIO, deployment latency/resources, stability, and independent B0–B4 evaluation remain pending. TensorRT is a follow-up, not a verified runtime.

The current targets are **20 November 2026** for model/configuration freeze, **25–27 November** for independent final evaluation, and **30 November** for development/evaluation completion. These are planned milestones, not completed results. See the [Master Project Plan](project-plan.md).

Most detailed records are in Korean, with configurations, hashes, tables, and machine-readable results in the linked reports. Contact: [22211897@yu.ac.kr](mailto:22211897@yu.ac.kr).
