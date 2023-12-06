const { parse, print } = require( 'recast' );
const { get } = require( 'lodash' );
const traverse = require( 'ast-traverse' );
const { readFileSync, writeFileSync } = require( 'fs' );

const source = readFileSync( 'sourceBefore.js', 'utf8' );

const ast = parse( source );

const REMOVE_LIST = ['screenshotMenuItem', 'fullScreenMenuItem', 'screenshotMenuItem', 'aboutMenuItem'];

traverse( ast, {
  pre: function preNode(node, parent, prop, idx) {
    if ( node.type === 'ObjectExpression' ) {
      const tandemProperty = node.properties.find( p => p.key.name === 'tandem' );
      if( REMOVE_LIST.includes(get(tandemProperty, "value.arguments[0].value") )) {
        console.log("Removing " + get(tandemProperty, "value.arguments[0].value"));
        parent.elements.splice( idx, 1 );
      }
    }
  }
});

const output = print( ast ).code;
writeFileSync( 'sourceAfter.js', output );
