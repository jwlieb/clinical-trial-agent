"""Unit tests for schemas.py - enum conversions and model validation."""

import pytest

from src.schemas import (
    TrialPhase,
    TrialStatus,
    StudyType,
    PatientProfile,
    EligibilityInfo,
    MatchLikelihood,
)


class TestTrialPhaseFromApi:
    """Tests for TrialPhase.from_api conversion."""
    
    def test_phase1_uppercase(self):
        """PHASE1 should convert to Phase 1."""
        assert TrialPhase.from_api("PHASE1") == TrialPhase.PHASE_1
    
    def test_phase2_uppercase(self):
        """PHASE2 should convert to Phase 2."""
        assert TrialPhase.from_api("PHASE2") == TrialPhase.PHASE_2
    
    def test_phase3_uppercase(self):
        """PHASE3 should convert to Phase 3."""
        assert TrialPhase.from_api("PHASE3") == TrialPhase.PHASE_3
    
    def test_phase4_uppercase(self):
        """PHASE4 should convert to Phase 4."""
        assert TrialPhase.from_api("PHASE4") == TrialPhase.PHASE_4
    
    def test_early_phase1(self):
        """EARLY_PHASE1 should convert to Early Phase 1."""
        assert TrialPhase.from_api("EARLY_PHASE1") == TrialPhase.EARLY_PHASE_1
    
    def test_na_to_not_applicable(self):
        """NA should convert to Not Applicable."""
        assert TrialPhase.from_api("NA") == TrialPhase.NOT_APPLICABLE
    
    def test_lowercase_works(self):
        """Lowercase input should be normalized."""
        assert TrialPhase.from_api("phase2") == TrialPhase.PHASE_2
    
    def test_unknown_returns_none(self):
        """Unknown phase values should return None."""
        assert TrialPhase.from_api("PHASE5") is None
        assert TrialPhase.from_api("INVALID") is None
        assert TrialPhase.from_api("") is None
    
    def test_value_accessor(self):
        """Enum value should return display string."""
        assert TrialPhase.PHASE_1.value == "Phase 1"
        assert TrialPhase.PHASE_1_2.value == "Phase 1/Phase 2"


class TestTrialStatusFromApi:
    """Tests for TrialStatus.from_api conversion."""
    
    def test_recruiting(self):
        """RECRUITING should convert to Recruiting."""
        assert TrialStatus.from_api("RECRUITING") == TrialStatus.RECRUITING
    
    def test_not_yet_recruiting(self):
        """NOT_YET_RECRUITING should convert correctly."""
        assert TrialStatus.from_api("NOT_YET_RECRUITING") == TrialStatus.NOT_YET_RECRUITING
    
    def test_active_not_recruiting(self):
        """ACTIVE_NOT_RECRUITING should convert correctly."""
        assert TrialStatus.from_api("ACTIVE_NOT_RECRUITING") == TrialStatus.ACTIVE_NOT_RECRUITING
    
    def test_completed(self):
        """COMPLETED should convert to Completed."""
        assert TrialStatus.from_api("COMPLETED") == TrialStatus.COMPLETED
    
    def test_terminated(self):
        """TERMINATED should convert to Terminated."""
        assert TrialStatus.from_api("TERMINATED") == TrialStatus.TERMINATED
    
    def test_withdrawn(self):
        """WITHDRAWN should convert to Withdrawn."""
        assert TrialStatus.from_api("WITHDRAWN") == TrialStatus.WITHDRAWN
    
    def test_suspended(self):
        """SUSPENDED should convert to Suspended."""
        assert TrialStatus.from_api("SUSPENDED") == TrialStatus.SUSPENDED
    
    def test_enrolling_by_invitation(self):
        """ENROLLING_BY_INVITATION should convert correctly."""
        assert TrialStatus.from_api("ENROLLING_BY_INVITATION") == TrialStatus.ENROLLING_BY_INVITATION
    
    def test_unknown_status(self):
        """Unknown status should return None."""
        assert TrialStatus.from_api("INVALID") is None
        assert TrialStatus.from_api("SOME_OTHER_STATUS") is None


class TestStudyTypeFromApi:
    """Tests for StudyType.from_api conversion."""
    
    def test_interventional(self):
        """INTERVENTIONAL should convert correctly."""
        assert StudyType.from_api("INTERVENTIONAL") == StudyType.INTERVENTIONAL
    
    def test_observational(self):
        """OBSERVATIONAL should convert correctly."""
        assert StudyType.from_api("OBSERVATIONAL") == StudyType.OBSERVATIONAL
    
    def test_expanded_access(self):
        """EXPANDED_ACCESS should convert correctly."""
        assert StudyType.from_api("EXPANDED_ACCESS") == StudyType.EXPANDED_ACCESS
    
    def test_unknown_returns_none(self):
        """Unknown study type should return None."""
        assert StudyType.from_api("REGISTRY") is None


class TestPatientProfileValidation:
    """Tests for PatientProfile model validation."""
    
    def test_minimal_patient(self):
        """Patient with only description should be valid."""
        patient = PatientProfile(description="Test patient")
        assert patient.description == "Test patient"
        assert patient.age is None
        assert patient.biomarkers == []
    
    def test_full_patient(self):
        """Patient with all fields should be valid."""
        patient = PatientProfile(
            age=65,
            sex="male",
            cancer_type="NSCLC",
            biomarkers=["KRAS G12C"],
            description="Full patient profile",
            ecog_status=1,
            prior_therapies=["chemo"],
        )
        assert patient.age == 65
        assert patient.ecog_status == 1
    
    def test_ecog_validation_range(self):
        """ECOG status should be 0-5."""
        # Valid ECOG values
        for ecog in range(6):
            patient = PatientProfile(description="test", ecog_status=ecog)
            assert patient.ecog_status == ecog
    
    def test_ecog_invalid_raises(self):
        """ECOG status outside 0-5 should raise validation error."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            PatientProfile(description="test", ecog_status=6)
        
        with pytest.raises(Exception):
            PatientProfile(description="test", ecog_status=-1)


class TestMatchLikelihood:
    """Tests for MatchLikelihood enum."""
    
    def test_values_exist(self):
        """All expected likelihood values should exist."""
        assert MatchLikelihood.HIGH.value == "HIGH"
        assert MatchLikelihood.MEDIUM.value == "MEDIUM"
        assert MatchLikelihood.LOW.value == "LOW"
        assert MatchLikelihood.EXCLUDED.value == "EXCLUDED"
        assert MatchLikelihood.UNKNOWN.value == "UNKNOWN"
    
    def test_from_string(self):
        """Should be able to create from string value."""
        assert MatchLikelihood("HIGH") == MatchLikelihood.HIGH
        assert MatchLikelihood("EXCLUDED") == MatchLikelihood.EXCLUDED

