"""KYC/AML compliance layer for trading platform."""
import os
from typing import Optional
from datetime import datetime
from sqlmodel import Session, select
from .database import UserProfileDB


class KYCService:
    """Know Your Customer (KYC) verification."""
    
    # Tier requirements
    TIER_LIMITS = {
        "bronze": {"daily_withdrawal": 500, "daily_deposit": 1000},
        "silver": {"daily_withdrawal": 5000, "daily_deposit": 10000},
        "gold": {"daily_withdrawal": 50000, "daily_deposit": 100000},
        "platinum": {"daily_withdrawal": 500000, "daily_deposit": 1000000},
    }
    
    @staticmethod
    def verify_user(user_id: str, email: str, session: Session) -> dict:
        """Initiate KYC verification for user."""
        statement = select(UserProfileDB).where(UserProfileDB.user_id == user_id)
        profile = session.exec(statement).first()
        
        if not profile:
            # Create new profile
            profile = UserProfileDB(user_id=user_id, email=email)
            session.add(profile)
            session.commit()
        
        return {
            "user_id": user_id,
            "kyc_status": profile.kyc_status,
            "kyc_verification_required": profile.kyc_status == "pending",
            "message": "Please complete KYC verification to trade"
        }
    
    @staticmethod
    def submit_kyc_info(user_id: str, kyc_data: dict, session: Session) -> dict:
        """Submit KYC information."""
        required_fields = ["full_name", "date_of_birth", "address", "document_id"]
        
        # Validate required fields
        missing = [f for f in required_fields if f not in kyc_data]
        if missing:
            return {"success": False, "error": f"Missing fields: {missing}"}
        
        # Simulate verification (in production, call KYC provider API)
        is_valid = KYCService._validate_kyc_data(kyc_data)
        
        if is_valid:
            statement = select(UserProfileDB).where(UserProfileDB.user_id == user_id)
            profile = session.exec(statement).first()
            if profile:
                profile.kyc_status = "verified"
                profile.account_tier = "silver"  # Default tier after KYC
                session.add(profile)
                session.commit()
                return {
                    "success": True,
                    "kyc_status": "verified",
                    "account_tier": profile.account_tier,
                }
        
        return {"success": False, "error": "KYC verification failed"}
    
    @staticmethod
    def _validate_kyc_data(kyc_data: dict) -> bool:
        """Validate KYC data format."""
        # In production, integrate with KYC provider (e.g., Onfido, Jumio)
        # For MVP, just validate format
        if not kyc_data.get("full_name") or len(kyc_data["full_name"]) < 3:
            return False
        if not kyc_data.get("document_id") or len(kyc_data["document_id"]) < 5:
            return False
        return True
    
    @staticmethod
    def get_tier_limits(account_tier: str) -> dict:
        """Get trading limits for account tier."""
        return KYCService.TIER_LIMITS.get(
            account_tier,
            KYCService.TIER_LIMITS["bronze"]
        )
    
    @staticmethod
    def can_deposit(user_id: str, amount: float, session: Session) -> dict:
        """Check if user can deposit given amount."""
        statement = select(UserProfileDB).where(UserProfileDB.user_id == user_id)
        profile = session.exec(statement).first()
        
        if not profile:
            return {"allowed": False, "reason": "User not found"}
        
        if profile.kyc_status != "verified":
            return {"allowed": False, "reason": "KYC verification required"}
        
        limits = KYCService.get_tier_limits(profile.account_tier)
        max_deposit = limits.get("daily_deposit", 1000)
        
        if amount > max_deposit:
            return {
                "allowed": False,
                "reason": f"Deposit exceeds daily limit of ${max_deposit}",
                "limit": max_deposit,
            }
        
        return {"allowed": True, "limit": max_deposit}
    
    @staticmethod
    def can_withdraw(user_id: str, amount: float, session: Session) -> dict:
        """Check if user can withdraw given amount."""
        statement = select(UserProfileDB).where(UserProfileDB.user_id == user_id)
        profile = session.exec(statement).first()
        
        if not profile:
            return {"allowed": False, "reason": "User not found"}
        
        if profile.kyc_status != "verified":
            return {"allowed": False, "reason": "KYC verification required"}
        
        if profile.total_balance < amount:
            return {
                "allowed": False,
                "reason": "Insufficient balance",
                "balance": profile.total_balance,
            }
        
        limits = KYCService.get_tier_limits(profile.account_tier)
        max_withdrawal = limits.get("daily_withdrawal", 500)
        
        if amount > max_withdrawal:
            return {
                "allowed": False,
                "reason": f"Withdrawal exceeds daily limit of ${max_withdrawal}",
                "limit": max_withdrawal,
            }
        
        return {"allowed": True, "limit": max_withdrawal}


class AMLService:
    """Anti-Money Laundering (AML) monitoring."""
    
    # AML risk thresholds
    HIGH_RISK_AMOUNT = 10000  # Transactions over $10k trigger extra monitoring
    SUSPICIOUS_PATTERN_THRESHOLD = 5  # 5+ transactions in short period
    
    @staticmethod
    def check_transaction(user_id: str, amount: float, transaction_type: str, session: Session) -> dict:
        """Check transaction for AML risks."""
        statement = select(UserProfileDB).where(UserProfileDB.user_id == user_id)
        profile = session.exec(statement).first()
        
        if not profile:
            return {"risk_level": "unknown", "allowed": False}
        
        risk_level = "low"
        flags = []
        
        # Check for high-value transactions
        if amount > AMLService.HIGH_RISK_AMOUNT:
            risk_level = "medium"
            flags.append(f"High-value transaction: ${amount}")
        
        # Check for suspicious patterns (rapid succession of large transactions)
        from .database import TransactionDB
        from sqlalchemy import and_
        from datetime import timedelta
        
        recent_statement = select(TransactionDB).where(
            and_(
                TransactionDB.user_id == user_id,
                TransactionDB.created_at >= datetime.utcnow() - timedelta(hours=1)
            )
        )
        recent_count = len(session.exec(recent_statement).all())
        
        if recent_count > AMLService.SUSPICIOUS_PATTERN_THRESHOLD:
            risk_level = "high"
            flags.append(f"Unusual activity: {recent_count} transactions in 1 hour")
        
        # Check account age (new accounts get extra scrutiny)
        if profile.created_at:
            age_days = (datetime.utcnow() - profile.created_at).days
            if age_days < 7:
                risk_level = "high" if risk_level == "medium" else "medium"
                flags.append(f"New account: {age_days} days old")
        
        return {
            "risk_level": risk_level,
            "allowed": risk_level != "high",
            "flags": flags,
            "aml_status": profile.aml_status,
        }
    
    @staticmethod
    def review_user(user_id: str, session: Session, action: str) -> dict:
        """Manual AML review (approve or flag user)."""
        statement = select(UserProfileDB).where(UserProfileDB.user_id == user_id)
        profile = session.exec(statement).first()
        
        if not profile:
            return {"success": False, "error": "User not found"}
        
        if action == "approve":
            profile.aml_status = "cleared"
        elif action == "flag":
            profile.aml_status = "flagged"
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
        
        session.add(profile)
        session.commit()
        
        return {
            "success": True,
            "user_id": user_id,
            "aml_status": profile.aml_status,
        }


class ComplianceMiddleware:
    """Unified compliance check for all transactions."""
    
    @staticmethod
    def verify_transaction(user_id: str, amount: float, transaction_type: str, session: Session) -> dict:
        """Run full compliance check (KYC + AML)."""
        # KYC check
        statement = select(UserProfileDB).where(UserProfileDB.user_id == user_id)
        profile = session.exec(statement).first()
        
        if not profile or profile.kyc_status != "verified":
            return {
                "allowed": False,
                "reason": "KYC verification required",
            }
        
        # AML check
        aml_result = AMLService.check_transaction(user_id, amount, transaction_type, session)
        if not aml_result["allowed"]:
            return {
                "allowed": False,
                "reason": f"AML check failed: {aml_result['flags']}",
                "risk_level": aml_result["risk_level"],
            }
        
        # Tier limit check
        if transaction_type == "deposit":
            kyc_result = KYCService.can_deposit(user_id, amount, session)
        else:  # withdrawal
            kyc_result = KYCService.can_withdraw(user_id, amount, session)
        
        return kyc_result
