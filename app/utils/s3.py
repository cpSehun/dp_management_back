import boto3
import logging
import os
from pathlib import Path
from botocore.exceptions import ClientError
from typing import Optional

# 로깅 설정
logger = logging.getLogger(__name__)

# S3 설정
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_FOLDER = os.getenv("S3_FOLDER", "generated-images")
CLOUDFRONT_DOMAIN_NAME = os.getenv("CLOUDFRONT_DOMAIN_NAME")

def get_s3_client():
    """S3 클라이언트 객체를 반환합니다.
    AWS_ACCESS_KEY_ID 및 AWS_SECRET_ACCESS_KEY 환경 변수가 설정되어 있으면 해당 키를 사용합니다.
    설정되어 있지 않으면, boto3의 기본 자격 증명 공급자 체인 (AWS SSO 프로필, EC2 인스턴스 프로필 등 포함)을 사용합니다.
    """
    try:
        if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
            logger.info("환경 변수에서 AWS Access Key를 사용하여 S3 클라이언트를 생성합니다.")
            s3_client = boto3.client(
                's3',
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                region_name=AWS_REGION  # client 생성 시에도 region_name 지정 가능
            )
        else:
            logger.info("boto3 기본 자격 증명 공급자 체인을 사용하여 S3 클라이언트를 생성합니다 (AWS SSO, IAM 역할 등).")
            # AWS_PROFILE 환경 변수가 설정되어 있으면 boto3.Session()이 자동으로 해당 프로필을 사용합니다.
            # region_name은 Session을 통해 전달하는 것이 좋습니다.
            session_params = {}
            if AWS_REGION:
                session_params['region_name'] = AWS_REGION
            
            # AWS_PROFILE 환경변수가 있다면 boto3.Session이 이를 사용합니다.
            # 명시적으로 프로필 이름을 코드에서 설정하고 싶다면:
            # aws_profile_name = os.getenv("AWS_PROFILE_NAME_FOR_APP") 
            # if aws_profile_name:
            #    session_params['profile_name'] = aws_profile_name
            
            session = boto3.Session(**session_params)
            s3_client = session.client('s3')
        
        # S3 클라이언트 생성 후 버킷 존재 여부 또는 접근 가능성 테스트 (선택 사항)
        # try:
        #     s3_client.head_bucket(Bucket=S3_BUCKET_NAME)
        #     logger.info(f"S3 버킷 '{S3_BUCKET_NAME}'에 접근 가능합니다.")
        # except ClientError as e:
        #     if e.response['Error']['Code'] == '404' or e.response['Error']['Code'] == 'NoSuchBucket':
        #         logger.error(f"S3 버킷 '{S3_BUCKET_NAME}'을 찾을 수 없습니다. 버킷 이름과 리전을 확인하세요.")
        #     elif e.response['Error']['Code'] == '403':
        #         logger.error(f"S3 버킷 '{S3_BUCKET_NAME}'에 접근할 권한이 없습니다. 자격 증명을 확인하세요.")
        #     else:
        #         logger.error(f"S3 버킷 접근 중 오류 발생: {e}")
        #     return None # 버킷 접근 불가 시 클라이언트 반환 안 함

        return s3_client
        
    except Exception as e:
        logger.error(f"S3 클라이언트 생성 실패: {e}", exc_info=True)
        return None

def upload_file_to_s3(file_path: Path, object_name: Optional[str] = None) -> Optional[str]:
    """
    파일을 S3 버킷에 업로드하고, CloudFront URL을 반환합니다.
    S3 객체는 비공개로 유지되며, CloudFront를 통해 접근합니다.
    
    Args:
        file_path (Path): 업로드할 로컬 파일 경로
        object_name (str, optional): S3에 저장될 객체 이름. None인 경우 file_path의 파일명 사용.
                                     S3_FOLDER가 설정되어 있으면 그 하위에 저장됩니다.
        
    Returns:
        Optional[str]: 업로드된 파일의 CloudFront URL, 실패 시 None
    """
    s3_client = get_s3_client()
    if not s3_client:
        logger.error("S3 클라이언트를 생성할 수 없습니다.")
        return None
    
    if not S3_BUCKET_NAME:
        logger.error("S3_BUCKET_NAME 환경 변수가 설정되지 않았습니다.")
        return None
        
    if not CLOUDFRONT_DOMAIN_NAME:
        logger.error("CLOUDFRONT_DOMAIN_NAME 환경 변수가 설정되지 않았습니다. CloudFront URL을 생성할 수 없습니다.")
        return None

    if object_name is None:
        object_name = file_path.name
    
    # S3_FOLDER가 설정되어 있으면 해당 폴더를 포함한 s3_key 생성
    # 이 s3_key는 CloudFront URL 경로에도 동일하게 사용됨
    s3_key = f"{S3_FOLDER}/{object_name}" if S3_FOLDER else object_name
    
    try:
        # 파일 업로드 시 ACL 설정을 제거 (객체는 비공개로 유지)
        # ContentType은 파일 유형에 맞게 설정하는 것이 좋음 (예: image/jpeg, image/png)
        # 여기서는 'image/png'로 고정했으나, 실제 파일 타입에 따라 동적으로 설정하는 것이 더 좋음
        s3_client.upload_file(
            str(file_path),
            S3_BUCKET_NAME,
            s3_key,
            ExtraArgs={'ContentType': 'image/png'} # ACL public-read 제거
        )
        
        # CloudFront URL 생성
        # CLOUDFRONT_DOMAIN_NAME은 "https://"를 포함하지 않아야 함
        # s3_key는 URL 인코딩이 필요할 수 있으나, 일반적인 파일명은 괜찮음
        cloudfront_url = f"https://{CLOUDFRONT_DOMAIN_NAME.strip('/')}/{s3_key}"
        logger.info(f"파일이 S3에 성공적으로 업로드되었고, CloudFront URL이 생성되었습니다: {cloudfront_url}")
        
        return cloudfront_url
    
    except ClientError as e:
        logger.error(f"S3 업로드 실패: {e}")
        return None
    except Exception as e:
        logger.error(f"파일 업로드 중 오류 발생: {e}")
        return None

def delete_file_from_s3(object_name: str) -> bool:
    """
    S3 버킷에서 파일을 삭제합니다. object_name은 S3_FOLDER를 포함한 전체 키여야 합니다.
    예: S3_FOLDER='images', object_name='my-image.png' -> 삭제할 키는 'images/my-image.png'
    프론트엔드/DB에서 관리하는 파일명이 object_name이 되고, S3_FOLDER와 조합하여 실제 s3_key를 만듭니다.
    이 함수에 전달되는 object_name은 이미 S3_FOLDER가 적용된 full key 이거나,
    또는 여기서 S3_FOLDER와 조합해야 합니다. 현재는 s3_key (S3_FOLDER 포함)를 받는다고 가정.
    """
    s3_client = get_s3_client()
    if not s3_client:
        logger.error("S3 클라이언트를 생성할 수 없습니다.")
        return False
    
    if not S3_BUCKET_NAME:
        logger.error("S3_BUCKET_NAME 환경 변수가 설정되지 않았습니다.")
        return False
    
    # object_name이 S3_FOLDER를 포함한 전체 키라고 가정.
    # 만약 object_name이 순수 파일명이라면 여기서 s3_key = f"{S3_FOLDER}/{object_name}" if S3_FOLDER else object_name 처리 필요.
    # 일관성을 위해 upload_file_to_s3와 동일한 s3_key 생성 로직을 사용하거나,
    # 이 함수는 항상 full s3_key를 받는 것으로 명확히 해야 함.
    # 현재 코드는 object_name이 full s3_key라고 가정하고 진행.
    # 예를 들어 DB에는 원래 파일명(예: myimage.png)만 저장하고, S3_FOLDER는 환경변수에서 읽어와서
    # 삭제 시점에 s3_key = f"{S3_FOLDER}/{db_filename}" 와 같이 조합할 수 있음.
    # 여기서는 `object_name`이 `s3_key`와 동일한 역할을 한다고 가정.
    s3_key_to_delete = object_name 

    try:
        s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_key_to_delete)
        logger.info(f"파일이 S3에서 성공적으로 삭제되었습니다: {s3_key_to_delete}")
        return True
    except ClientError as e:
        logger.error(f"S3 삭제 실패: {e}")
        return False
    except Exception as e:
        logger.error(f"파일 삭제 중 오류 발생: {e}")
        return False 