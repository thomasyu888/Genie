import os
import logging
import pandas as pd
import process_functions
import example_filetype_format
from functools import partial

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validateSymbol(x, bedDf, returnMappedDf=True):
    valid=False
    gene = x['HUGO_SYMBOL']
    if sum(bedDf['Hugo_Symbol'] == gene) > 0:
        valid=True
    elif sum(bedDf['ID'] == gene) > 0:
        mismatch = bedDf[bedDf['ID'] == gene]
        mismatch.drop_duplicates(inplace=True)
        logger.info("%s will be remapped to %s" % (gene, mismatch['Hugo_Symbol'].values[0]))
        x['HUGO_SYMBOL'] = mismatch['Hugo_Symbol'].values[0]
    else:
        logger.warning("%s cannot be remapped and will not be released. The symbol must exist in your seq assay ids (bed files) and must be mappable to a gene." % gene)
        x['HUGO_SYMBOL'] = pd.np.nan
        #x['FUSION'] = x['FUSION'].replace("%s-" % gene,"%s-" % x['HUGO_SYMBOL'])
        #x['COMMENTS'] = str(x['COMMENTS']).replace("-%s" % gene,"-%s" % str(x['COMMENTS']))
    if returnMappedDf:
        return(x)
    else:
        return(valid)

# Remap fusion's FUSION column
def remapFusion(gene_dict, DF, col):
    nonmapped = []
    total = []
    for each in DF[col]:
        for key in gene_dict:
            value = gene_dict[key]
            if value == False:
                nonmapped.append(key)
            else:
                each = each.replace("%s-" % key, "%s-" % value)
                each = each.replace("-%s fusion" % key, "-%s fusion" % value)
        total.append(each)
    DF[col] = total 
    return(DF, nonmapped)

class fusions(example_filetype_format.FileTypeFormat):
   
    _fileType = "fusions"

    _process_kwargs = ["newPath", "databaseSynId",'test']

    _validation_kwargs = ['testing','noSymbolCheck']

    #VALIDATE FILENAME
    def _validateFilename(self, filePath):
        assert os.path.basename(filePath[0]) == "data_fusions_%s.txt" % self.center


    def _process(self, fusion, test=False):
        fusion.columns = [col.upper() for col in fusion.columns]
        fusion['CENTER'] = self.center
        newsamples = [process_functions.checkGenieId(i,self.center) for i in fusion['TUMOR_SAMPLE_BARCODE']]
        fusion['TUMOR_SAMPLE_BARCODE'] = newsamples

        if fusion.get("COMMENTS") is None:
            fusion['COMMENTS'] = ""

        fusion['COMMENTS'] = fusion['COMMENTS'].fillna("")
        fusion['ENTREZ_GENE_ID'] = fusion['ENTREZ_GENE_ID'].fillna(0)
        fusion = fusion.drop_duplicates()
        fusion['ID'] = fusion['HUGO_SYMBOL'].copy()
        bedSynId = process_functions.getDatabaseSynId(self.syn, "bed", test=test)
        bed = self.syn.tableQuery("select Hugo_Symbol, ID from %s where CENTER = '%s'" % (bedSynId, self.center))
        bedDf = bed.asDataFrame()
        fusion = fusion.apply(lambda x: validateSymbol(x, bedDf), axis=1)
        #Create nonmapped gene dict
        temp = fusion[fusion['HUGO_SYMBOL'] != fusion['ID']]
        foo = temp[~temp.HUGO_SYMBOL.isnull()]
        temp = foo[['HUGO_SYMBOL','ID']]
        temp.drop_duplicates(inplace=True)
        temp.index=temp.ID
        del temp['ID']
        # fusion = fusion[~fusion['HUGO_SYMBOL'].isnull()]
        fusion['FUSION'] = fusion['FUSION'].fillna("")
        fusion, nonmapped = remapFusion(temp.to_dict()['HUGO_SYMBOL'], fusion, "FUSION")
        fusion, nonmapped = remapFusion(temp.to_dict()['HUGO_SYMBOL'], fusion, "COMMENTS")
        fusion['ENTREZ_GENE_ID'] = [int(float(i)) for i in fusion['ENTREZ_GENE_ID']]
        return(fusion)

    #PROCESSING
    def process_steps(self, filePath, **kwargs):
        logger.info('PROCESSING %s' % filePath)
        databaseSynId = kwargs['databaseSynId']
        newPath = kwargs['newPath']
        test = kwargs['test']
        cols = ['HUGO_SYMBOL','ENTREZ_GENE_ID','CENTER','TUMOR_SAMPLE_BARCODE','FUSION','DNA_SUPPORT','RNA_SUPPORT','METHOD','FRAME','COMMENTS','ID']

        fusion = pd.read_csv(filePath, sep="\t",comment="#")
        fusion = self._process(fusion, test)
        process_functions.updateData(self.syn, databaseSynId, fusion[cols], self.center, cols, toDelete=True)
        fusion.to_csv(newPath, sep="\t",index=False)
        return(newPath)

    def _validate(self, fusionDF, noSymbolCheck, test=False):
        total_error = ""
        warning = ""

        fusionDF.columns = [col.upper() for col in fusionDF.columns]

        REQUIRED_HEADERS = pd.Series(['HUGO_SYMBOL','ENTREZ_GENE_ID','CENTER','TUMOR_SAMPLE_BARCODE','FUSION','DNA_SUPPORT','RNA_SUPPORT','METHOD','FRAME'])
        if fusionDF.get("COMMENTS") is None:
            fusionDF['COMMENTS'] = ""
        if not all(REQUIRED_HEADERS.isin(fusionDF.columns)):
            total_error += "Your fusion file must at least have these headers: %s.\n" % ",".join(REQUIRED_HEADERS[~REQUIRED_HEADERS.isin(fusionDF.columns)])
        if process_functions.checkColExist(fusionDF, "HUGO_SYMBOL") and not noSymbolCheck:
           # logger.info("VALIDATING %s GENE SYMBOLS" % os.path.basename(filePath))
            #invalidated_genes = fusionDF["HUGO_SYMBOL"].drop_duplicates().apply(validateSymbol)
            bedSynId = process_functions.getDatabaseSynId(self.syn, "bed", test=test)
            bed = self.syn.tableQuery("select Hugo_Symbol, ID from %s where CENTER = '%s'" % (bedSynId, self.center))
            bedDf = bed.asDataFrame()
            #invalidated_genes = self.pool.map(process_functions.validateSymbol, fusionDF["HUGO_SYMBOL"].drop_duplicates())
            fusionDF = fusionDF.drop_duplicates("HUGO_SYMBOL").apply(lambda x: validateSymbol(x, bedDf), axis=1)
            if fusionDF["HUGO_SYMBOL"].isnull().any():
                warning += "Any gene names that can't be remapped will be removed.\n"
        return(total_error, warning)

    #VALIDATION
    def validate_steps(self, filePathList, **kwargs):
        """
        This function validates the Fusion file to make sure it adhere to the genomic SOP.
        
        :params filePath:     Path to Fusion file

        :returns:             Text with all the errors in the Fusion file
        """
        filePath = filePathList[0]
        logger.info("VALIDATING %s" % os.path.basename(filePath))
        test = kwargs['testing']
        noSymbolCheck = kwargs['noSymbolCheck']
        fusionDF = pd.read_csv(filePath,sep="\t",comment="#")
        return(self._validate(fusionDF,noSymbolCheck,test))