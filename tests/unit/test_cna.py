import synapseclient
import pandas as pd
import mock
from nose.tools import assert_raises
import os
import sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(SCRIPT_DIR,"../../processing"))

from cna import cna

def test_processing():
	def createMockTable(dataframe):
		table = mock.create_autospec(synapseclient.table.CsvFileTable)
		table.asDataFrame.return_value= dataframe
		return(table)

	def table_query_results(*args):
		return(table_query_results_map[args])
	databaseMapping = pd.DataFrame(dict(Database=['bed'],
										Id=['syn8457748']))
	symbols = pd.DataFrame(dict(Hugo_Symbol=['AAK1','AAED1','AAAS'],
								ID=['AAK1', 'AAED', 'AAAS']))
	#This is the gene positions that all bed dataframe will be processed against
	table_query_results_map = {
	("SELECT * FROM syn10967259",) : createMockTable(databaseMapping),
	("select Hugo_Symbol, ID from syn8457748 where CENTER = 'SAGE'",) : createMockTable(symbols),
	}   

	syn = mock.create_autospec(synapseclient.Synapse) 
	syn.tableQuery.side_effect=table_query_results

	cnaClass = cna(syn, "SAGE")
	order = ["Hugo_Symbol","Entrez_gene_id","GENIE-SAGE-ID1-1","GENIE-SAGE-ID2-1"]

	expectedCnaDf = pd.DataFrame(dict(TUMOR_SAMPLE_BARCODE =['GENIE-SAGE-ID1-1', 'GENIE-SAGE-ID2-1'],
									  CNAData =["AAED1,AAK1,AAAS\n1,2,0", "AAED1,AAK1,AAAS\n2,1,-1"],
									  CENTER =['SAGE','SAGE'],
									  unmappedData =[float('nan'),float('nan')]))


	cnaDf = pd.DataFrame({"Hugo_Symbol":['AAED', 'AAK1', 'AAAS'],
						  "Entrez_gene_id":[0,0,0],
						  "GENIE-SAGE-ID1-1":[1, 2, 0],
						  "GENIE-SAGE-ID2-1":[2, 1, -1]})
	cnaDf = cnaDf[order]
	newCnaDf = cnaClass._process(cnaDf)
	assert expectedCnaDf.equals(newCnaDf[expectedCnaDf.columns])
	
	expectedCnaDf = pd.DataFrame(dict(TUMOR_SAMPLE_BARCODE =['GENIE-SAGE-ID1-1',"GENIE-SAGE-ID2-1"],
									  CNAData =["AAED1\n1","AAED1\n"],
									  CENTER =['SAGE','SAGE'],
									  unmappedData =["foo\n0","foo\n-1"]))

	cnaDf = pd.DataFrame({"Hugo_Symbol":['AAED', 'AAED1', 'foo'],
						  "Entrez_gene_id":[0,0,0],
						  "GENIE-SAGE-ID1-1":[1, 1, 0],
						  "GENIE-SAGE-ID2-1":[2, 0, -1]})
	cnaDf = cnaDf[order]
	newCnaDf = cnaClass._process(cnaDf)
	assert expectedCnaDf.equals(newCnaDf[expectedCnaDf.columns])

def test_validation():
	def createMockTable(dataframe):
		table = mock.create_autospec(synapseclient.table.CsvFileTable)
		table.asDataFrame.return_value= dataframe
		return(table)

	def table_query_results(*args):
		return(table_query_results_map[args])
	databaseMapping = pd.DataFrame(dict(Database=['bed'],
										Id=['syn8457748']))
	symbols = pd.DataFrame(dict(Hugo_Symbol=['AAK1','AAED1','AAAS','AAED1'],
								ID=['AAK1', 'AAED', 'AAAS','AAD']))
	#This is the gene positions that all bed dataframe will be processed against
	table_query_results_map = {
	("SELECT * FROM syn10967259",) : createMockTable(databaseMapping),
	("select Hugo_Symbol, ID from syn8457748 where CENTER = 'SAGE'",) : createMockTable(symbols),
	}   


	syn = mock.create_autospec(synapseclient.Synapse) 
	syn.tableQuery.side_effect=table_query_results

	cnaClass = cna(syn, "SAGE")

	assert_raises(AssertionError, cnaClass.validateFilename, ["foo"])
	assert cnaClass.validateFilename(["data_CNA_SAGE.txt"]) == "cna"

	order = ["Hugo_Symbol","Entrez_gene_id","GENIE-SAGE-ID1-1","GENIE-SAGE-ID2-1"]
	cnaDf = pd.DataFrame({"Hugo_Symbol":['AAED', 'AAK1', 'AAAS'],
						  "Entrez_gene_id":[0,0,0],
						  "GENIE-SAGE-ID1-1":[1, 2, 0],
						  "GENIE-SAGE-ID2-1":[2, 1, -1]})
	cnaDf = cnaDf[order]
	error, warning = cnaClass._validate(cnaDf, False)
	assert error == ""
	assert warning == ""

	cnaDf = pd.DataFrame({"Hugo_Symbol":['foo', 'AAED', 'AAED1','AAD'],
						  "GENIE-SAGE-ID1-1":[1, 2, float('nan'),1],
						  "GENIE-SAGE-ID2-1":[2, 1, -1,2]})
	cnaDf.sort_values("Hugo_Symbol",inplace=True)
	cnaDf = cnaDf[["GENIE-SAGE-ID1-1","Hugo_Symbol","GENIE-SAGE-ID2-1"]]
	
	error, warning = cnaClass._validate(cnaDf, False)
	expectedErrors = ("Your cnv file's first column must be Hugo_symbol\n"
					  "Your cnv file must not have any empty values\n"
					  "Your CNA file has duplicated Hugo_Symbols (After remapping of genes): AAD,AAED,AAED1 -> AAED1,AAED1,AAED1.\n")

	assert error == expectedErrors
	assert warning == ""
	order = ["Hugo_Symbol","GENIE-SAGE-ID1-1","GENIE-SAGE-ID2-1"]

	cnaDf = pd.DataFrame({"Hugo_Symbol":['AAK1', 'AAAS', 'AAED1'],
						  "GENIE-SAGE-ID1-1":[1, 2, 1],
						  "GENIE-SAGE-ID2-1":[2, 1, "foo"]})
	cnaDf = cnaDf[order]
	error, warning = cnaClass._validate(cnaDf, False)
	expectedErrors = ("All values must be numerical values\n")
	assert error == expectedErrors
	assert warning == ""