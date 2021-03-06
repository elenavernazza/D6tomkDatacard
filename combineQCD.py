#!/usr/bin/env python
import os
import argparse
import sys
from glob import glob
import numpy as np
import ROOT 
from copy import deepcopy
from makeDummies import *
from configparser import ConfigParser

def fillDict(dict_, base_folder, prefix, models):
    for folder in glob(base_folder + "/*/"):
        op = folder.split(base_folder + "/" + prefix + "_")[-1].strip("/")
        if "_" in op:
            # Dosomething when 2D
            pass 

        dict_[op] = {} 

        for model in  models:
            if os.path.isfile(folder + model+ "/rootFile/histos.root"):
                dict_[op][model] = folder + model+ "/rootFile/histos.root"
            else:
                sys.exit("Missing histograms for {}".format(folder  + model+ "/rootFile/histos.root"))

    return

def mkdir(p):
   try:
      os.mkdir(p)
   except:
      return 

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Command line parser for ewk QCD combination')
    parser.add_argument('--ewk',     dest='ewk',     help='Base folder for ewk BEFORE mkDatacards', required = True)
    parser.add_argument('--qcd',     dest='qcd',     help='Base folder for QCD BEFORE mkDatacards', required = True)
    parser.add_argument('--outprocess',     dest='outprocess',     help='Name of the final process', required = True)
    parser.add_argument('--cfg',     dest='cfg',     help='Give one config for parents processes in order to generate dummy Latinos files, or create a new one with only "d_" fields', required = True)
    parser.add_argument('--prefix_ewk',     dest='prefix_ewk',     help='Prefix of EWK folder including channel name separated by _ eg to_Latinos_SSWW', required = False, default="to_Latinos")
    parser.add_argument('--prefix_qcd',     dest='prefix_qcd',     help='Prefix of QCD folder including channel name separated by _ eg to_Latinos_OSWWQCD', required = False, default="to_Latinos")
    parser.add_argument('--models',     dest='models',     help='models to be extracted', required = False, default = "EFT,EFTNeg,EFTNeg-alt")
    parser.add_argument('--outfolder',     dest='outfolder',     help='outfolder name', required = False, default="Combined_EWK_QCD")
    parser.add_argument('--qcdAsbkg',     dest='qcdAsbkg',     help='Always add the SM QCD shape as an additional bkg. No QCD dependence on EFT. Default False', default=False, action="store_true")

    args = parser.parse_args()

    ROOT.gROOT.SetBatch(1)

    models = args.models.split(",")

    #read dummy config, used only for dummy files
    config = ConfigParser(converters={'list': lambda x: [str(i.strip()) for i in x.split(',')]})
    config.read(args.cfg)

    # Defining useful variables

    ewk_channel = args.prefix_ewk.split("_")[-1]
    qcd_channel = args.prefix_qcd.split("_")[-1]

    ewkDict =  { }
    qcdDict =  { }

    fillDict(ewkDict, args.ewk, args.prefix_ewk, models)
    fillDict(qcdDict, args.qcd, args.prefix_qcd, models)

    # Folder with most of the operators. For missing ones, the QCD will be appended as a background (separately)
    majorDict, majorProc = (ewkDict, ewk_channel) if len(ewkDict.keys()) > len(qcdDict.keys()) else (qcdDict, qcd_channel)
    minorDict, minorProc = (ewkDict, ewk_channel) if len(ewkDict.keys()) <= len(qcdDict.keys()) else (qcdDict, qcd_channel)

    # as SM is equal for all the op we just retrieve the first for  each variable
    # from the minority dict. we store it for each

    fallBack = {}
    for model in models:
        fallBack[model] = {}
        op = minorDict.keys()[0]
        f = ROOT.TFile(minorDict[minorDict.keys()[0]][model])
        d = f.Get(minorProc + "_" + op) # this is related to the file structure after mkDCInput.py
        variables = [i.GetName() for i in d.GetListOfKeys()]
        for var in variables:
            fallBack[model][var] = deepcopy( f.Get(minorProc + "_" + op + "/" + var + "/histo_sm") )

        f.Close()


    # Beginning the combination

    mkdir(args.outfolder)

    # Logging results for checks
    added = []
    sole = []

    for op in majorDict.keys():
        mkdir(args.outfolder + "/to_Latinos_" + args.outprocess + "_" + op )
        for model in models:
            
            outPath = args.outfolder + "/to_Latinos_" + args.outprocess + "_" + op + "/" + model
            mkdir( outPath)
            mkdir(outPath + "/rootFile" )

            fOut = ROOT.TFile(outPath + "/rootFile/histos.root", "RECREATE")
            fOut.mkdir(args.outprocess + "_" + op + "/")

            fMaj = ROOT.TFile(majorDict[op][model])
            dMaj = fMaj.Get(majorProc + "_" + op)
            varMaj = [i.GetName() for i in dMaj.GetListOfKeys()]

            if not args.qcdAsbkg:

                if op in minorDict.keys():

                    if op not in added: added.append(op)

                    fMin = ROOT.TFile(minorDict[op][model])
                    dMin = fMin.Get(minorProc + "_" + op)
                    varMin = [i.GetName() for i in dMin.GetListOfKeys()]

                    if not all(i in varMaj for i in varMin):
                        sys.exit("[ERROR] Found different variables for {} and {},\
                                    check you inputs".format(majorDict[op][model], minorDict[op][model]))
                    
                    finalVars = list(varMaj)
                    # At this point vars are  equal so wecycle on either one
                    for var in varMaj:

                        fOut.mkdir(args.outprocess + "_" + op  + "/" + var + "/")
                        fOut.cd(args.outprocess + "_" + op  + "/" + var + "/")

                        dCMaj = fMaj.Get(majorProc + "_" + op + "/" + var)
                        dCMin = fMin.Get(minorProc + "_" + op + "/" + var )

                        compMaj = [i.GetName() for i in dCMaj.GetListOfKeys()]
                        compMin = [i.GetName() for i in dCMin.GetListOfKeys()]

                        if not all(i in compMaj for i in compMin):
                            sys.exit("[ERROR] Found different components for {} and {}, check you inputs".format(majorDict[op][model], minorDict[op][model]))

                        finalComponent = [i.split("histo_")[1] for i in compMaj]

                        #at this point components are  equal so wecycle on either one
                        for comp in compMaj:
                            hMaj = deepcopy( fMaj.Get(majorProc + "_" + op + "/" + var + "/" + comp) )
                            hMin = deepcopy( fMin.Get(minorProc + "_" + op + "/" + var + "/" + comp) )
                            #print("First Integral: {} Second Integral: {}".format(hMaj.Integral(), hMin.Integral()))
                            hMaj.Add(hMin)
                            #print("Summed Integral: {}".format(hMaj.Integral()))

                            hMaj.Write(comp)

                # May happen that op are sswapped (in 2D ) ssuch as (cHl1, cW) and (cW, cHl1), 
                # of course the set is sharedd and shapes should be summed
                elif "_".join(op.split("_")[::-1]) in minorDict.keys():
                    op_min = "_".join(op.split("_")[::-1])
                    op_maj = op

                    print(op_min, op_maj)

                    if op not in added: added.append(op)

                    fMin = ROOT.TFile(minorDict[op_min][model])
                    dMin = fMin.Get(minorProc + "_" + op_min)
                    varMin = [i.GetName() for i in dMin.GetListOfKeys()]

                    if not all(i in varMaj for i in varMin):
                        sys.exit("[ERROR] Found different variables for {} and {},\
                                    check you inputs".format(majorDict[op_maj][model], minorDict[op_min][model]))
                    
                    finalVars = list(varMaj)
                    # At this point vars are  equal so wecycle on either one
                    for var in varMaj:

                        fOut.mkdir(args.outprocess + "_" + op_maj  + "/" + var + "/")
                        fOut.cd(args.outprocess + "_" + op_maj  + "/" + var + "/")

                        dCMaj = fMaj.Get(majorProc + "_" + op_maj + "/" + var)
                        dCMin = fMin.Get(minorProc + "_" + op_min + "/" + var )

                        compMaj = [i.GetName() for i in dCMaj.GetListOfKeys()]
                        compMin = [i.GetName() for i in dCMin.GetListOfKeys()]


                        if not all(i in compMaj for i in compMin):
                            sys.exit("[ERROR] Found different components for {} and {}, check you inputs".format(majorDict[op_maj][model], minorDict[op_min][model]))

                        finalComponent = [i.split("histo_")[1] for i in compMaj]

                        #at this point components are  equal so wecycle on either one
                        for comp in compMaj:
                            hMaj = deepcopy( fMaj.Get(majorProc + "_" + op_maj + "/" + var + "/" + comp) )
                            hMin = deepcopy( fMin.Get(minorProc + "_" + op_min + "/" + var + "/" + comp) )
                            # print("@ Component: {}".format(comp))
                            # print("First Integral: {} Second Integral: {}".format(hMaj.Integral(), hMin.Integral()))
                            hMaj.Add(hMin)
                            # print("Summed Integral: {}".format(hMaj.Integral()))

                            # default name is hMaj key coherent with all the directory names
                            hMaj.Write(comp)

                else:
                    if op not in sole: sole.append(op)
                    if not all(i in varMaj for i in fallBack[model].keys()):
                        sys.exit("[ERROR] Found different variables for {} and the fallback SM,\
                                        check you inputs".format(majorDict[op][model]))
                    finalVars = list(varMaj)
                    for var in varMaj:
                        fOut.mkdir(args.outprocess + "_" + op + "/" + var + "/")
                        fOut.cd(args.outprocess + "_" + op + "/" + var + "/")

                        dCMaj = fMaj.Get(majorProc + "_" + op + "/" + var)
                        compMaj = [i.GetName() for i in dCMaj.GetListOfKeys()]

                        finalComponent = [i.split("histo_")[1] for i in compMaj]
                        finalComponent.append("QCD_" + minorProc)

                        #Just copy the major  dict component
                        for comp in compMaj:
                            hMaj = deepcopy( fMaj.Get(majorProc + "_" + op + "/" + var + "/" + comp) )
                            hMaj.Write(comp)
                        
                        # And append the SM component with a name != from combine model names
                        hSM_bkg = fallBack[model][var]
                        #god knows why Write does not overwrite object name...
                        hSM_bkg.SetName("histo_QCD_" + minorProc)
                        hSM_bkg.Write("histo_QCD_" + minorProc)

            #if args.qcdAsbkg then always add QCD SM shap as bkg         
            else:
                if op not in sole: sole.append(op)
                if not all(i in varMaj for i in fallBack[model].keys()):
                    sys.exit("[ERROR] Found different variables for {} and the fallback SM,\
                                    check you inputs".format(majorDict[op][model]))
                finalVars = list(varMaj)
                for var in varMaj:
                    fOut.mkdir(args.outprocess + "_" + op + "/" + var + "/")
                    fOut.cd(args.outprocess + "_" + op + "/" + var + "/")

                    dCMaj = fMaj.Get(majorProc + "_" + op + "/" + var)
                    compMaj = [i.GetName() for i in dCMaj.GetListOfKeys()]

                    finalComponent = [i.split("histo_")[1] for i in compMaj]
                    finalComponent.append("QCD_" + minorProc)

                    #Just copy the major  dict component
                    for comp in compMaj:
                        hMaj = deepcopy( fMaj.Get(majorProc + "_" + op + "/" + var + "/" + comp) )
                        hMaj.Write(comp)
                    
                    # And append the SM component with a name != from combine model names
                    hSM_bkg = fallBack[model][var]
                    #god knows why Write does not overwrite object name...
                    hSM_bkg.SetName("histo_QCD_" + minorProc)
                    hSM_bkg.Write("histo_QCD_" + minorProc)


            print("op: {} {}".format(op, finalComponent))
            fOut.Write()
            fOut.Close()

            # Generate Dummies
            sample = args.outprocess + "_"+ op #just to make a dict name compatible with dummy maker
            print("[INFO] Generating dummies ...")
            if config.get("d_structure", "makeDummy") == "True"        : makeStructure({sample: finalComponent}, model, outPath, isMkDC = False)
            if config.get("d_plot", "makeDummy") == "True"             : makePlot({sample: finalComponent}, model, config, outPath, isMkDC = False)
            if config.get("d_samples", "makeDummy") == "True"          : makeSamples({sample: finalComponent}, model, config, outPath, isMkDC = False)
            if config.get("d_configuration", "makeDummy") == "True"    : makeConfiguration({sample: finalComponent}, model, config, outPath)
            if config.get("d_alias", "makeDummy") == "True"            : makeAliases({sample: finalComponent}, model, outPath)
            if config.get("d_cuts", "makeDummy") == "True"             : makeCuts({sample: finalComponent}, model, outPath)
            if config.get("d_variables", "makeDummy") == "True"        : makeVariables({sample: dict.fromkeys(finalVars)}, model, config, outPath)
            if config.get("d_nuisances", "makeDummy") == "True"        : makeNuisances({sample: finalComponent}, model, config, outPath, isMkDC = False)
            
            
    print("[INFO] Conclusions ...")
    print("The following ops are shared and contributions summed {}: {}".format(len(added), added))
    print("The following ops are not shared. Contributions only from SM as bkg {}: {}".format(len(sole), sole))
