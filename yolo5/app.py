import time
from pathlib import Path
from detect import run
import yaml
from loguru import logger
import os
import boto3
import requests

import json
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from decimal import Decimal
from pathlib import Path

images_bucket = os.environ['BUCKET_NAME'] #shantal-awsproject
queue_name = os.environ['SQS_QUEUE_NAME'] #shantal-queue-aws

# queue_url= os.environ['https://sqs.us-east-2.amazonaws.com/019273956931/shantal-queue-aws']

# Initialize AWS clients
sqs_client = boto3.client('sqs', region_name='us-east-2')
s3_client = boto3.client('s3', region_name='us-east-2')
dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
table = dynamodb.Table('shantal-dynamoDB-aws') # Set the table name

# A CHANGE 20
with open("data/coco128.yaml", "r") as stream:
    names = yaml.safe_load(stream)['names']

# The yolo5 takes the photo from the queue and saves the results to dynamoDB:
# Acts as a consumer: consumes the jobs from the queue, downloads the image from S3, processes the image, and writes the results to a DynamoDB table
def consume():
    while True:
        try:
            response = sqs_client.receive_message(
                QueueUrl="https://sqs.us-east-2.amazonaws.com/019273956931/shantal-queue-aws",
                MaxNumberOfMessages=1,
                WaitTimeSeconds=5)

            if 'Messages' in response:
                num_messages = len(response['Messages'])
                logger.info(f'Number of messages received: {num_messages}')

                message = json.loads(response['Messages'][0]['Body'])
                receipt_handle = response['Messages'][0]['ReceiptHandle']
                prediction_id = response['Messages'][0]['MessageId']

                logger.info(f'prediction id: {prediction_id}. start processing')
                logger.info(f'Received message:')
                logger.info(f'{message}')
                img_name = message['file_name']  # TODO extract from `message`
                 # ['imgName']
                object_key = message['object_key']  # stores the path of the images on s3 (/data/img1-12312312)
                chat_id = message['chat_id']  # TODO extract from `message`

                if num_messages > 0 and img_name and chat_id:
                    try:
                        # Extract image name and chat ID from the message
                        logger.info(f'img_name: {img_name}')
                    except KeyError as e:
                        logger.error(f'Missing key in message: {e}')  # did not find keys
                        sqs_client.delete_message(QueueUrl=queue_name, ReceiptHandle=receipt_handle)
                        continue

                    # TODO download img_name from S3, store the local image path in original_img_path -------------

                    photos_dir = Path('/home/ubuntu/INTPolybotServiceAWS/yolo5/photos')
                    photos_dir.mkdir(parents=True, exist_ok=True)  # Creates the directory if it doesn't exist

                    image_name_s3 = object_key.split("/")[-1]
                    logger.info(f'image_name_s3: {image_name_s3}')
                    original_img_path = f'{photos_dir}/{image_name_s3}' # /home/ubuntu/INTPolybotServiceAWS/yolo5/photos/ + image_name_s3
                    logger.info(f'Download path: {original_img_path}')

                    try:
                        # Download Image from S3
                        s3_client.download_file(images_bucket, object_key, str(original_img_path))

                        logger.info(f'Download image from s3 completed')

                        if Path(original_img_path).exists(): # Verify the file exists after download
                            logger.info(f'Image successfully downloaded to {original_img_path}')
                        else:
                            logger.error(f'Image not found at {original_img_path} after download')

                    except Exception as e:
                        logger.error(f'Failed to download image from S3: {e}')
                        raise

                    # Predicts the objects in the image (YOLOv5 object detection)
                    run(
                        weights='yolov5s.pt',
                        data='data/coco128.yaml',
                        source=original_img_path,
                        project='static/data',
                        name=prediction_id,
                        save_txt=True
                    )

                    logger.info(f'-----------> PREDICTION IMAGE IS DONE <-----------')

                    # TODO Uploads the predicted image (predicted_img_path) to S3 (be careful not to override the original image). ------------------------------------

                    predicted_img_path = Path(
                        f'static/data/{prediction_id}/{image_name_s3}')  # predicted_img_path = to the predicted image. static/data/ = path to be saved locally
                    # run this on ec2: mkdir -p static/data/
                    s3_client.upload_file(str(predicted_img_path), images_bucket,
                                          f'predictions/{image_name_s3}')  # uploads the predicted image to s3
                    logger.info(f' >>>>> Upload predicted image to s3 - path predictions COMPLETE <<<<< ')

                    image_name_s3_txt = image_name_s3.replace('.jpg', '.txt')
                    # Parse prediction labels and create a summary
                    # pred_summary_path = Path(f'static/data/{prediction_id}/labels/{original_img_path}.txt')
                    pred_summary_path = Path(f'static/data/{prediction_id}/labels/{image_name_s3_txt}')

                    logger.info(f'pred_summary_path: {pred_summary_path}')

                    if pred_summary_path.exists():
                        with open(pred_summary_path) as f:
                            labels = f.read().splitlines()
                            labels = [line.split(' ') for line in labels]
                            labels = [{
                                'class': names[int(l[0])],
                                'cx': Decimal(l[1]),  # Convert to Decimal
                                'cy': Decimal(l[2]),  # Convert to Decimal
                                'width': Decimal(l[3]),  # Convert to Decimal
                                'height': Decimal(l[4]),  # Convert to Decimal
                            } for l in labels]

                        prediction_summary = {
                            'prediction_id': prediction_id,
                            'chat_id': chat_id,  # Include chat_id in the summary
                            'original_img_path': str(original_img_path),
                            'predicted_img_path': str(predicted_img_path),
                            'labels': labels,
                            'time': Decimal(time.time())  # Convert to Decimal
                        }

                        # TODO store the prediction_summary in a DynamoDB table ---------------------------------------------------

                        table.put_item(Item=prediction_summary)
                        logger.info(f'SAVED PREDICTION SUMMARY to DynamoDB')
                        logger.info(f'=========> Prediction summary: {prediction_summary}')
                        time.sleep(3)  # Add a delay

                        # TODO perform a GET request to Polybot to `/results` endpoint ---------------------------------------------------

                        callback_url = 'http://shantal-aws-alb-1835467939.us-east-2.elb.amazonaws.com/results'  # YOLO5 will send a POST request to this URL CHECK
                        try:
                            # Perform the GET request to the `/results` endpoint with the predictionId as a query parameter
                            logger.info(f'TRY TO PERFORM A GET REQUEST 1: {callback_url}?predictionId={prediction_id}')
                          # response = requests.get(callback_url, params={'predictionId': prediction_id}, timeout=10)  # Timeout after 10 seconds
                            if prediction_id:
                                response = requests.get(f"{callback_url}?predictionId={prediction_id}")
                                logger.info(f'prediction_id is: {prediction_id}')
                            else:
                                logger.info(f'prediction_id is none.')
                                logger.error("prediction_id is missing")

                            logger.info(f'TRY TO PERFORM A GET REQUEST 2')

                            # Check if the request was successful
                            if response.status_code == 200:
                                logger.info(f'STATUS CODE = 200')
                                results = response.json()  # Assuming the response is in JSON format
                                logger.info(
                                    f'Successfully fetched results for prediction_id {prediction_id}: {results}')
                            else:
                                logger.info(f'INFO 1: Failed to fetch results. Status code: {response.status_code}, Response: {response.text}')
                                logger.error(f'Failed to fetch results. Status code: {response.status_code}, Response: {response.text}')


                        except requests.exceptions.RequestException as e:
                            logger.info(f'INFO 2: An error occurred while fetching results: {e}')
                            logger.error(f'An error occurred while fetching results: {e}')

                        # TODO Delete the message from the queue as the job is considered as DONE ---------------------------------------------------
                        sqs_client.delete_message(QueueUrl=queue_name, ReceiptHandle=receipt_handle)
                        logger.info(f'prediction id: {prediction_id}. -----> message deleted from queue')

                    else:
                        logger.info(f'prediction: {prediction_id}/{original_img_path} prediction result not found')

        except Exception as e:
            logger.info({e})

        time.sleep(1)


if __name__ == "__main__":
    consume()
