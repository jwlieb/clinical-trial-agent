"""Shared fixtures for tests."""

import pytest
from datetime import date

from src.schemas import (
    PatientProfile,
    Trial,
    EligibilityInfo,
    MatchLikelihood,
)


@pytest.fixture
def sample_patient() -> PatientProfile:
    """Sample patient profile for testing."""
    return PatientProfile(
        age=65,
        sex="male",
        cancer_type="NSCLC",
        biomarkers=["KRAS G12C"],
        description="65-year-old male with advanced NSCLC, KRAS G12C positive. "
                    "Previously treated with platinum-based chemotherapy and pembrolizumab. "
                    "ECOG 1, no brain metastases.",
        ecog_status=1,
        prior_therapies=["platinum chemotherapy", "pembrolizumab"],
        brain_mets_status="none",
    )


@pytest.fixture
def sample_trial() -> Trial:
    """Sample recruiting trial for testing."""
    return Trial(
        nct_id="NCT12345678",
        title="A Phase 2 Study of Drug X in KRAS G12C NSCLC",
        phase="Phase 2",
        status="Recruiting",
        study_type="Interventional",
        conditions=["Non-Small Cell Lung Cancer", "KRAS G12C Mutation"],
        interventions=["Drug X"],
        sponsor="Test Pharma Inc",
        enrollment_count=100,
        start_date=date(2024, 1, 1),
        locations=["United States", "Canada"],
        summary="A study testing Drug X in patients with KRAS G12C mutated NSCLC.",
        source_url="https://clinicaltrials.gov/study/NCT12345678",
        eligibility=EligibilityInfo(
            raw_text="Inclusion: KRAS G12C mutation, advanced NSCLC, ECOG 0-1. "
                     "Exclusion: Active brain metastases.",
            minimum_age="18 Years",
            maximum_age="85 Years",
            sex="ALL",
            accepts_healthy_volunteers=False,
        ),
    )


@pytest.fixture
def non_recruiting_trial(sample_trial: Trial) -> Trial:
    """Trial that is not recruiting."""
    return sample_trial.model_copy(update={"status": "Completed"})


@pytest.fixture
def female_only_trial(sample_trial: Trial) -> Trial:
    """Trial that only accepts females."""
    new_eligibility = sample_trial.eligibility.model_copy(update={"sex": "FEMALE"})
    return sample_trial.model_copy(update={"eligibility": new_eligibility})


@pytest.fixture
def age_restricted_trial(sample_trial: Trial) -> Trial:
    """Trial with strict age limits."""
    new_eligibility = sample_trial.eligibility.model_copy(
        update={"minimum_age": "18 Years", "maximum_age": "50 Years"}
    )
    return sample_trial.model_copy(update={"eligibility": new_eligibility})


@pytest.fixture
def raw_trial_api_response() -> dict:
    """Sample raw API response from ClinicalTrials.gov."""
    return {
        "protocolSection": {
            "identificationModule": {
                "nctId": "NCT99999999",
                "officialTitle": "Test Trial Official Title",
                "briefTitle": "Test Trial",
            },
            "statusModule": {
                "overallStatus": "RECRUITING",
                "startDateStruct": {"date": "2024-06-15"},
                "completionDateStruct": {"date": "2026-12-31"},
            },
            "designModule": {
                "studyType": "INTERVENTIONAL",
                "phases": ["PHASE2"],
                "enrollmentInfo": {"count": 200, "type": "ESTIMATED"},
            },
            "conditionsModule": {
                "conditions": ["Lung Cancer", "NSCLC"],
            },
            "armsInterventionsModule": {
                "interventions": [
                    {"name": "Drug ABC", "type": "DRUG"},
                    {"name": "Placebo", "type": "DRUG"},
                ],
            },
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": "Pharma Corp"},
                "collaborators": [
                    {"name": "Research Institute"},
                ],
            },
            "contactsLocationsModule": {
                "locations": [
                    {"country": "United States", "city": "Boston"},
                    {"country": "United States", "city": "New York"},
                    {"country": "Germany", "city": "Berlin"},
                ],
            },
            "descriptionModule": {
                "briefSummary": "This is a test trial summary.",
            },
            "eligibilityModule": {
                "eligibilityCriteria": "Inclusion criteria here. Exclusion criteria here.",
                "minimumAge": "21 Years",
                "maximumAge": "70 Years",
                "sex": "ALL",
                "healthyVolunteers": "false",
            },
        }
    }

