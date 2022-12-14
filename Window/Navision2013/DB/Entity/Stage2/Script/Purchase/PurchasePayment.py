from pyspark import SparkConf, SparkContext
from pyspark.sql import SQLContext, SparkSession
from pyspark.sql.types import *
from datetime import date
import datetime as dt
import os,sys
from os.path import dirname, join, abspath
st = dt.datetime.now()
Kockpit_Path =abspath(join(join(dirname(__file__),'..','..','..','..','..')))
DB_path =abspath(join(join(dirname(__file__),'..','..','..','..')))
sys.path.insert(0,'../../')
sys.path.insert(0, DB_path)
from Configuration.AppConfig import * 
from Configuration.Constant import *
from Configuration.udf import *
from Configuration import udf as Kockpit

Filepath = os.path.dirname(os.path.abspath(__file__))
FilePathSplit = Filepath.split('\\')
DBName = FilePathSplit[-5]
EntityName = FilePathSplit[-4]
DBEntity = DBName+EntityName
entityLocation = DBName+EntityName
STAGE1_PATH=Kockpit_Path+"/" +DBName+"/" +EntityName+"/" +"Stage1/ParquetData"
STAGE2_PATH=Kockpit_Path+"/" +DBName+"/" +EntityName+"/" +"Stage2/ParquetData"
conf = SparkConf().setMaster("local[16]").setAppName("PurchasePayment").\
                    set("spark.sql.shuffle.partitions",16).\
                    set("spark.serializer", "org.apache.spark.serializer.KryoSerializer").\
                    set("spark.local.dir", "/tmp/spark-temp").\
                    set("spark.driver.memory","30g").\
                    set("spark.executor.memory","30g").\
                    set("spark.driver.cores",16).\
                    set("spark.driver.maxResultSize","0").\
                    set("spark.sql.debug.maxToStringFields", "1000").\
                    set("spark.executor.instances", "20").\
                    set('spark.scheduler.mode', 'FAIR').\
                    set("spark.sql.broadcastTimeout", "36000").\
                    set("spark.network.timeout", 10000000).\
                    set("spark.sql.legacy.parquet.datetimeRebaseModeInWrite", "LEGACY").\
                    set("spark.sql.legacy.parquet.datetimeRebaseModeInRead", "LEGACY").\
                    set("spark.sql.legacy.parquet.datetimeRebaseModeInRead", "CORRECTED").\
                    set("spark.sql.legacy.timeParserPolicy","LEGACY").\
                    set("spark.sql.legacy.parquet.int96RebaseModeInWrite","LEGACY").\
                    set("spark.sql.legacy.parquet.int96RebaseModeInWrite","CORRECTED")
sc = SparkContext(conf = conf)
sqlCtx = SQLContext(sc)
spark = sqlCtx.sparkSession
for dbe in config["DbEntities"]:
    if dbe['ActiveInactive']=='true' and  dbe['Location']==DBEntity:
        CompanyName=dbe['Name']
        CompanyName=CompanyName.replace(" ","")
        try:
            
            logger = Logger()
            entityLocation = DBName+EntityName
            VLE=spark.read.format("parquet").load(STAGE1_PATH+"/Vendor Ledger Entry")
            DVLE=spark.read.format("parquet").load(STAGE1_PATH+"/Detailed Vendor Ledg_ Entry")
            pih =spark.read.format("parquet").load(STAGE1_PATH+"/Purch_ Inv_ Header")
            pih=pih.select("NO_","PaymentTermsCode")
            cond = [DVLE.VendorLedgerEntryNo_ == VLE.EntryNo_]
            PurchasePayment = Kockpit.LJOIN(DVLE,VLE,cond)
            PurchasePayment = PurchasePayment.withColumn("AmountLCY",PurchasePayment["AmountLCY"]*(-1))
            PurchasePayment = Kockpit.RenameDuplicateColumns(PurchasePayment)
            cond2=[PurchasePayment.DocumentNo__1 == pih.NO_]
            PurchasePayment=Kockpit.LJOIN(PurchasePayment,pih,cond2)
            PurchasePayment.coalesce(1).write.format("parquet").mode("overwrite").option("overwriteSchema", "true").save(STAGE2_PATH+"/"+"Purchase/PurchasePayment")
            logger.endExecution()
         
            try:
                IDEorBatch = sys.argv[1]
            except Exception as e :
                IDEorBatch = "IDLE"
            log_dict = logger.getSuccessLoggedRecord("Purchase.PurchasePayment", DBName, EntityName, PurchasePayment.count(), len(PurchasePayment.columns), IDEorBatch)
            log_df = spark.createDataFrame(log_dict, logger.getSchema())
            log_df.write.jdbc(url=PostgresDbInfo.PostgresUrl, table="logs.logs", mode='append', properties=PostgresDbInfo.props)
        
        except Exception as ex:
            exc_type,exc_value,exc_traceback=sys.exc_info()
            print("Error:",ex)
            print("type - "+str(exc_type))
            print("File - "+exc_traceback.tb_frame.f_code.co_filename)
            print("Error Line No. - "+str(exc_traceback.tb_lineno))
            logger.endExecution()
            try:
                IDEorBatch = sys.argv[1]
            except Exception as e :
                IDEorBatch = "IDLE"
            os.system("spark-submit "+Kockpit_Path+"/Email.py 1 PurchasePayment '"+CompanyName+"' "+DBEntity+" "+str(exc_traceback.tb_lineno)+" ")
                    
            log_dict = logger.getErrorLoggedRecord('Purchase.PurchasePayment', DBName, EntityName, str(ex), str(exc_traceback.tb_lineno), IDEorBatch)
            log_df = spark.createDataFrame(log_dict, logger.getSchema())
            log_df.write.jdbc(url=PostgresDbInfo.PostgresUrl, table="logs.logs", mode='append', properties=PostgresDbInfo.props)
print('purchase_PurchasePayment completed: ' + str((dt.datetime.now()-st).total_seconds()))
