# This script builds the help directory from README.md file (in the root directory)
# It requires jekyll being installed and configured

# Make sure that we're running the script from the local directory
echo $0
cd `dirname "$0"`


echo This script will overwrite the 'help' directory. Do you want to proceed? [y/N]
read answer
if [[ "$answer" == "y" || "$answer" == "Y" ]] ; then
    mkdir -p build-docs
    cp ../README.md build-docs/
    cp screenshot.png build-docs
    cp _config.yml build-docs
    cd build-docs
    jekyll build
    HELP_DIR="../../help"
    mkdir -p $HELP_DIR
    cp _site/README.html $HELP_DIR/
    cp _site/screenshot.png $HELP_DIR/
    mkdir -p $HELP_DIR/assets
    cp -r _site/assets/main.css $HELP_DIR/assets/main.css

    # Correct '/assets' bug that prevents correct display
    cd $HELP_DIR
    pwd
    cat README.html | sed -e 's/\/assets/assets/g' > README2.html
    mv README2.html README.html


    # or
    #jekyll serve --incremental
else
    echo "Aborting"
fi
